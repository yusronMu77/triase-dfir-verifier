"""Pasangkan paket kode (triage) dan draf narasi (narrative), periksa, lalu terbitkan `card.verified`.

Urutan kedatangan kedua event tidak dijamin, jadi masing-masing disimpan di tabel tunggu sampai pasangannya ada.
Kunci advisory per kartu membuat dua konsumen tidak saling melewatkan pasangan. Percobaan 1 dengan klaim gagal
menerbitkan `narration.retry_requested` dan menunggu draf percobaan 2 (note app-verifier 5.2). Hasil,
`card.verified`, dan `audit.record` ditulis dalam satu transaksi (outbox). Teks bukti tidak disimpan; cukup ID dan
kode gagal.
"""

from __future__ import annotations

from datetime import UTC, datetime

from astria_common.audit_client import audit_event
from astria_common.events import new_event
from astria_common.log import get_logger
from astria_common.outbox import enqueue
from astria_contracts import Envelope
from astria_contracts.events.card_skeleton_created import CardSkeletonCreated, Kode
from astria_contracts.events.narration_completed import NarrationCompleted
from pydantic import BaseModel
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    SmallInteger,
    Table,
    Text,
    delete,
    func,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncConnection

from astria_verifier.checks import periksa
from astria_verifier.evidence import JEDA_ULANG, EvidenceSource, ambil_bukti
from astria_verifier.policy import (
    CHECKER_VERSION,
    POLICY_VERSION,
    evidence_set_hash,
    perlu_ulang,
    permintaan_ulang,
    putuskan,
)

log = get_logger(__name__)

metadata = MetaData()

paket_tunggu = Table(
    "paket_tunggu",
    metadata,
    Column("card_id", Text, primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("paket", JSONB, nullable=False),
    Column("diterima_pada", DateTime(timezone=True), nullable=False, server_default=func.now()),
    # Terisi saat narration.retry_requested diterbitkan (status MINTA_ULANG, note app-verifier 5.3).
    Column("diminta_ulang_pada", DateTime(timezone=True), nullable=True),
)
draf_tunggu = Table(
    "draf_tunggu",
    metadata,
    Column("card_id", Text, primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("attempt", SmallInteger, primary_key=True),
    Column("draf", JSONB, nullable=False),
    Column("diterima_pada", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
verifikasi = Table(
    "verifikasi",
    metadata,
    Column("card_id", Text, primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("status", Text, nullable=False),
    Column("percobaan", SmallInteger, nullable=False),
    Column("klaim_total", Integer, nullable=False),
    Column("klaim_lolos", Integer, nullable=False),
    Column("policy_version", Text, nullable=False),
    Column("checker_version", Text, nullable=False),
    Column("evidence_set_hash", Text, nullable=False),
    Column("diperiksa_pada", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
klaim_hasil = Table(
    "klaim_hasil",
    metadata,
    Column("card_id", Text, primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("attempt", SmallInteger, primary_key=True),
    Column("klaim_index", Integer, primary_key=True),
    Column("jenis", Text, nullable=False),
    Column("lulus", Boolean, nullable=False),
    Column("kode_gagal", JSONB, nullable=False),
)


def _kartu(envelope: Envelope) -> tuple[str, int]:
    card_id, version = envelope.correlation.card_id, envelope.correlation.version
    if card_id is None or version is None:
        raise ValueError(f"{envelope.type} tanpa correlation card_id/version")
    return card_id, version


class Verifier:
    """Handler dua konsumen: `card.skeleton.created` (paket) dan `narration.completed` (draf)."""

    def __init__(self, evidence: EvidenceSource, *, ambang: float, jeda_bukti: float = JEDA_ULANG) -> None:
        self._evidence = evidence
        self._ambang = ambang
        self._jeda_bukti = jeda_bukti

    async def on_paket(self, conn: AsyncConnection, envelope: Envelope, data: BaseModel) -> None:
        assert isinstance(data, CardSkeletonCreated)
        card_id, version = _kartu(envelope)
        await self._lock(conn, card_id, version)
        await conn.execute(
            insert(paket_tunggu)
            .values(card_id=card_id, version=version, paket=data.model_dump(mode="json"))
            .on_conflict_do_nothing()
        )
        await self._coba_periksa(conn, card_id, version, envelope.trace_id)

    async def on_draf(self, conn: AsyncConnection, envelope: Envelope, data: BaseModel) -> None:
        assert isinstance(data, NarrationCompleted)
        card_id, version = _kartu(envelope)
        await self._lock(conn, card_id, version)
        await conn.execute(
            insert(draf_tunggu)
            .values(card_id=card_id, version=version, attempt=data.attempt, draf=data.model_dump(mode="json"))
            .on_conflict_do_nothing()
        )
        await self._coba_periksa(conn, card_id, version, envelope.trace_id)

    @staticmethod
    async def _lock(conn: AsyncConnection, card_id: str, version: int) -> None:
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"{card_id}:{version}"})

    @staticmethod
    async def _bersihkan(conn: AsyncConnection, kunci: dict) -> None:
        await conn.execute(delete(paket_tunggu).filter_by(**kunci))
        await conn.execute(delete(draf_tunggu).filter_by(**kunci))

    async def _coba_periksa(self, conn: AsyncConnection, card_id: str, version: int, trace_id: str) -> None:
        kunci = {"card_id": card_id, "version": version}
        if (await conn.execute(select(verifikasi.c.status).filter_by(**kunci))).first() is not None:
            await self._bersihkan(conn, kunci)
            log.info("kartu_sudah_diperiksa", **kunci)
            return
        paket = (
            await conn.execute(select(paket_tunggu.c.paket, paket_tunggu.c.diminta_ulang_pada).filter_by(**kunci))
        ).first()
        draf = (
            await conn.execute(
                select(draf_tunggu.c.draf, draf_tunggu.c.attempt)
                .filter_by(**kunci)
                .order_by(draf_tunggu.c.attempt.desc())
                .limit(1)
            )
        ).first()
        if paket is None or draf is None:
            log.info("menunggu_pasangan", paket=paket is not None, draf=draf is not None, **kunci)
            return
        if draf.attempt == 1 and paket.diminta_ulang_pada is not None:
            log.info("menunggu_percobaan_2", **kunci)
            return

        kode = Kode.model_validate(paket.paket["kode"])
        narasi = NarrationCompleted.model_validate(draf.draf)
        bukti = await ambil_bukti(self._evidence, [b.id.root for b in kode.bukti], jeda=self._jeda_bukti)
        hasil = periksa(kode, narasi.narasi, bukti)
        await conn.execute(
            klaim_hasil.insert(),
            [
                {
                    **kunci,
                    "attempt": narasi.attempt,
                    "klaim_index": h.klaim.index,
                    "jenis": h.klaim.jenis,
                    "lulus": h.lulus,
                    "kode_gagal": list(h.kode_gagal),
                }
                for h in hasil
            ],
        )
        if perlu_ulang(hasil, narasi.attempt):
            permintaan = permintaan_ulang(hasil)
            await conn.execute(update(paket_tunggu).filter_by(**kunci).values(diminta_ulang_pada=func.now()))
            await enqueue(
                conn, new_event("narration.retry_requested", permintaan, correlation=kunci, trace_id=trace_id)
            )
            log.info("minta_percobaan_2", kegagalan=len(permintaan.kegagalan), **kunci)
            return

        kep = putuskan(kode, narasi.narasi, hasil, self._ambang)
        set_hash = evidence_set_hash(kode)
        await conn.execute(
            verifikasi.insert().values(
                **kunci,
                status=kep.status,
                percobaan=narasi.attempt,
                klaim_total=kep.klaim_total,
                klaim_lolos=kep.klaim_lolos,
                policy_version=POLICY_VERSION,
                checker_version=CHECKER_VERSION,
                evidence_set_hash=set_hash,
            )
        )
        await enqueue(
            conn,
            new_event(
                "card.verified",
                {
                    "status": kep.status,
                    "percobaan": narasi.attempt,
                    "klaim_total": kep.klaim_total,
                    "klaim_lolos": kep.klaim_lolos,
                    "ditolak": kep.ditolak,
                    "policy_version": POLICY_VERSION,
                    "checker_version": CHECKER_VERSION,
                    "model_terperiksa": narasi.model.model_id,
                    "evidence_set_hash": set_hash,
                    "dokumen": {**kunci, "kode": kode.model_dump(mode="json"), "model": kep.model},
                },
                correlation=kunci,
                trace_id=trace_id,
            ),
        )
        await enqueue(
            conn,
            audit_event(
                {
                    "idempotency_key": f"verifier:{card_id}:{version}",
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "actor": "svc:verifier",
                    "actor_type": "service",
                    "action": "card.verify",
                    "target_type": "card",
                    "target_id": f"{card_id}/v{version}",
                    "via": "system",
                    "payload": {
                        "status": kep.status,
                        "percobaan": narasi.attempt,
                        "policy_version": POLICY_VERSION,
                        "evidence_set_hash": set_hash,
                    },
                },
                correlation=kunci,
            ),
        )
        await self._bersihkan(conn, kunci)
        log.info("kartu_diperiksa", status=kep.status, lolos=kep.klaim_lolos, total=kep.klaim_total, **kunci)
