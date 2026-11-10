"""Periksa satu draf tanpa NATS dan basis data (untuk lab eval dan demo).

Pemakaian: `python -m astria_verifier.cli --paket paket.json --draf draf.json [--bukti bukti.json]`.
`paket` = data atau amplop `card.skeleton.created`; `draf` = data atau amplop `narration.completed`;
`bukti` = jawaban ingest `{items, not_found}`. Keluaran JSON identik untuk masukan identik.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from astria_contracts.events.card_skeleton_created import CardSkeletonCreated
from astria_contracts.events.narration_completed import NarrationCompleted

from astria_verifier.checks import periksa
from astria_verifier.evidence import parse_items
from astria_verifier.policy import evidence_set_hash, putuskan


def _data(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw["data"] if "data" in raw and "type" in raw else raw


def run(paket: Path, draf: Path, bukti: Path | None) -> dict[str, Any]:
    kode = CardSkeletonCreated.model_validate(_data(paket)).kode
    narasi = NarrationCompleted.model_validate(_data(draf)).narasi
    sumber = parse_items(json.loads(bukti.read_text(encoding="utf-8"))) if bukti else None
    hasil = periksa(kode, narasi, sumber)
    kep = putuskan(kode, narasi, hasil)
    return {
        "status": kep.status,
        "klaim_total": kep.klaim_total,
        "klaim_lolos": kep.klaim_lolos,
        "bukti_asli_dibaca": sumber is not None,
        "evidence_set_hash": evidence_set_hash(kode),
        "klaim": [
            {"index": h.klaim.index, "jenis": h.klaim.jenis, "teks": h.klaim.teks, "kode_gagal": list(h.kode_gagal)}
            for h in hasil
        ],
        "model": kep.model,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="astria-verifier-periksa", description=__doc__.splitlines()[0])
    parser.add_argument("--paket", type=Path, required=True)
    parser.add_argument("--draf", type=Path, required=True)
    parser.add_argument("--bukti", type=Path)
    args = parser.parse_args(argv)
    json.dump(run(args.paket, args.draf, args.bukti), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
