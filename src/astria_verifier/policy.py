"""Kebijakan hasil (note app-verifier 5.7): minta ulang, lalu LULUS, SEBAGIAN, atau TEMPLAT, dan dokumen kartu.

Percobaan 1 yang punya klaim gagal belum diputuskan (`perlu_ulang`): narrative diminta menulis percobaan 2 lewat
`narration.retry_requested` yang hanya berisi indeks klaim dan kode gagal. `putuskan` hanya mengembalikan status
final.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from astria_contracts.events.card_skeleton_created import Kode
from astria_contracts.events.narration_completed import Narasi
from astria_contracts.events.narration_retry_requested import Kegagalan, NarrationRetryRequested

from astria_verifier.checks import HasilKlaim

POLICY_VERSION = "verifikasi-1.1.0"
CHECKER_VERSION = "verifier-0.2.0"
AMBANG_SEBAGIAN = 0.70


@dataclass(frozen=True)
class Keputusan:
    status: str
    klaim_total: int
    klaim_lolos: int
    ditolak: list[dict[str, Any]]
    model: dict[str, Any]


def evidence_set_hash(kode: Kode) -> str:
    lines = sorted(f"{b.id.root}:{b.sha256}" for b in kode.bukti)
    return "sha256:" + hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _model_setelah_kebijakan(kode: Kode, narasi: Narasi, hasil: list[HasilKlaim]) -> dict[str, Any]:
    """Klaim gagal dibuang; hipotesis utama yang gagal diganti judul kartu dengan semua bukti kartu."""
    lulus = {h.klaim.posisi: h.lulus for h in hasil}
    data = narasi.model_dump(mode="json")
    utama = data["hipotesis_utama"]
    if not lulus[("hipotesis_utama", 0)]:
        utama = {"teks": kode.judul, "bukti": [b.id.root for b in kode.bukti]}
    tandingan = [
        {**h, "pembantah": h["pembantah"] if lulus.get(("pembantah", i), False) else ""}
        for i, h in enumerate(data["hipotesis_tandingan"])
        if lulus[("tandingan", i)]
    ]
    return {
        "ringkasan": [k for i, k in enumerate(data["ringkasan"]) if lulus[("ringkasan", i)]],
        "hipotesis_utama": utama,
        "hipotesis_tandingan": tandingan,
        "belum_diketahui": [b for i, b in enumerate(data["belum_diketahui"]) if lulus[("belum_diketahui", i)]],
    }


def perlu_ulang(hasil: list[HasilKlaim], percobaan: int) -> bool:
    return percobaan == 1 and any(not h.lulus for h in hasil if h.klaim.dihitung)


def permintaan_ulang(hasil: list[HasilKlaim]) -> NarrationRetryRequested:
    """Isi `narration.retry_requested`: indeks klaim dan kode gagal, tanpa teks klaim atau kutipan log."""
    gagal = [Kegagalan(klaim_no=h.klaim.index, kode=k) for h in hasil for k in h.kode_gagal]
    return NarrationRetryRequested(attempt=2, kegagalan=gagal)


def putuskan(kode: Kode, narasi: Narasi, hasil: list[HasilKlaim], ambang: float = AMBANG_SEBAGIAN) -> Keputusan:
    dihitung = [h for h in hasil if h.klaim.dihitung]
    lolos = sum(h.lulus for h in dihitung)
    ditolak = [{"klaim_index": h.klaim.index, "kode_gagal": list(h.kode_gagal)} for h in dihitung if not h.lulus]
    if dihitung and lolos == len(dihitung):
        status = "LULUS"
    elif dihitung and lolos / len(dihitung) >= ambang:
        status = "SEBAGIAN"
    else:
        status = "TEMPLAT"
    # TEMPLAT: narasi model dibuang seluruhnya; tampilan menyusun teks dari `kode`.
    model = {} if status == "TEMPLAT" else _model_setelah_kebijakan(kode, narasi, hasil)
    return Keputusan(status, len(dihitung), lolos, ditolak, model)
