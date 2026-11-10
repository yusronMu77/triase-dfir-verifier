"""Uji integrasi dengan PostgreSQL sungguhan (`ASTRIA_TEST_DATABASE_URL`, tersedia di kontainer py devenv)."""

from __future__ import annotations

import os
import uuid

import orjson
import pytest
from astria_common import outbox
from astria_common.db import Database
from astria_common.events import decode, encode, new_event
from astria_contracts import example
from helpers import bukti_asli
from pydantic import SecretStr
from sqlalchemy import func, select, text

from astria_verifier.pipeline import Verifier, draf_tunggu, klaim_hasil, metadata, paket_tunggu, verifikasi
from astria_verifier.policy import AMBANG_SEBAGIAN

DB_URL = os.environ.get("ASTRIA_TEST_DATABASE_URL")
KARTU = {"card_id": "IC-20261110-003", "version": 1}

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not DB_URL, reason="ASTRIA_TEST_DATABASE_URL tidak diisi")]


class FakeEvidence:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def fetch(self, ids):
        self.calls.append(list(ids))
        return bukti_asli()


@pytest.fixture
async def db():
    schema = f"t_{uuid.uuid4().hex[:8]}"
    database = Database(SecretStr(DB_URL or ""), schema=schema, metadata=[outbox.metadata, metadata])
    await database.start()
    await database.wait_ready(10)
    yield database
    async with database.engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    await database.stop()


def _event(event_type: str):
    return decode(encode(new_event(event_type, example(event_type)["data"], correlation=KARTU)))


async def _run(db: Database, handler, event) -> None:
    async with db.engine.begin() as conn:
        await handler(conn, *event)


async def _count(conn, table) -> int:
    return (await conn.execute(select(func.count()).select_from(table))).scalar()


async def _outbox(db: Database) -> list:
    async with db.engine.connect() as conn:
        rows = (await conn.execute(select(outbox.outbox.c.envelope).order_by(outbox.outbox.c.created_at))).all()
    return [decode(orjson.dumps(r.envelope)) for r in rows]


@pytest.mark.parametrize("order", ["paket_dulu", "draf_dulu"])
async def test_pair_in_any_order_publishes_card_verified_and_audit(db: Database, order: str) -> None:
    evidence = FakeEvidence()
    v = Verifier(evidence, ambang=AMBANG_SEBAGIAN)
    steps = [(v.on_paket, _event("card.skeleton.created")), (v.on_draf, _event("narration.completed"))]
    for handler, event in steps if order == "paket_dulu" else reversed(steps):
        await _run(db, handler, event)

    published = await _outbox(db)
    assert [e.type for e, _ in published] == ["card.verified", "audit.record"]
    verified = published[0][1]
    assert verified.dokumen.card_id == KARTU["card_id"]
    assert verified.model_terperiksa == "replay-cache"
    assert (verified.status, verified.klaim_total, verified.klaim_lolos) == ("LULUS", 4, 4)
    assert evidence.calls == [["EV-hb01-004217", "EV-hb01-004231"]]
    async with db.engine.connect() as conn:
        assert await _count(conn, paket_tunggu) == 0
        assert await _count(conn, draf_tunggu) == 0
        row = (await conn.execute(select(verifikasi))).one()
        assert row.status == verified.status and row.bukti_asli_dibaca is True
        assert await _count(conn, klaim_hasil) == 5


async def test_redelivered_draft_after_verification_does_not_publish_again(db: Database) -> None:
    v = Verifier(None, ambang=AMBANG_SEBAGIAN)
    await _run(db, v.on_paket, _event("card.skeleton.created"))
    await _run(db, v.on_draf, _event("narration.completed"))
    await _run(db, v.on_draf, _event("narration.completed"))  # id event baru, kartu sama

    assert [e.type for e, _ in await _outbox(db)] == ["card.verified", "audit.record"]
    async with db.engine.connect() as conn:
        assert await _count(conn, draf_tunggu) == 0
        assert (await conn.execute(select(verifikasi.c.bukti_asli_dibaca))).scalar() is False
