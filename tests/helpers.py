"""Data uji dari contoh kontrak (rantai svc-backup)."""

from __future__ import annotations

from typing import Any

from astria_contracts import example
from astria_contracts.events.card_skeleton_created import CardSkeletonCreated, Kode
from astria_contracts.events.narration_completed import Narasi

from astria_verifier.checks import Bukti

EV1, EV2 = "EV-hb01-004217", "EV-hb01-004231"


def kode() -> Kode:
    return CardSkeletonCreated.model_validate(example("card.skeleton.created")["data"]).kode


def sha(ev: str) -> str:
    return next(b.sha256 for b in kode().bukti if b.id.root == ev)


def bukti_asli() -> dict[str, Bukti]:
    return {
        EV1: Bukti(sha(EV1), {"TargetUserName": "svc-backup", "SrcIP": "10.20.8.31"}, ("WS-ADM-04", "WS-HR-11")),
        EV2: Bukti(sha(EV2), {"TargetUserName": "svc-backup", "LogonType": "3"}, ("WS-ADM-04",)),
    }


def narasi(ringkasan: list[dict[str, Any]] | None = None, **overrides: Any) -> Narasi:
    data: dict[str, Any] = {
        "ringkasan": ringkasan
        if ringkasan is not None
        else [{"klaim": "Akun svc-backup mengalami 20 kegagalan logon.", "bukti": [EV1]}],
        "hipotesis_utama": {"teks": "Akun layanan svc-backup diduga diambil alih.", "bukti": [EV2]},
        "hipotesis_tandingan": [],
        "belum_diketahui": [],
    }
    return Narasi.model_validate(data | overrides)


def klaim(teks: str, bukti: list[str] | None = None, nilai: dict[str, str] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"klaim": teks, "bukti": bukti or [EV1]}
    if nilai is not None:
        out["nilai_dikutip"] = nilai
    return out
