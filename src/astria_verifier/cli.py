"""Periksa satu draf tanpa NATS dan basis data (untuk lab eval dan demo).

Pemakaian: `python -m astria_verifier.cli --paket paket.json --draf draf.json --bukti bukti.json`.
`paket` = data atau amplop `card.skeleton.created`; `draf` = data atau amplop `narration.completed`;
`bukti` = jawaban ingest `{items, not_found}`. Status mengikuti `attempt` di draf: percobaan 1 dengan klaim gagal
menghasilkan `MINTA_ULANG` beserta isi `kegagalan`. Keluaran JSON identik untuk masukan identik.
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
from astria_verifier.policy import evidence_set_hash, perlu_ulang, permintaan_ulang, putuskan


def _data(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw["data"] if "data" in raw and "type" in raw else raw


def run(paket: Path, draf: Path, bukti: Path) -> dict[str, Any]:
    kode = CardSkeletonCreated.model_validate(_data(paket)).kode
    draf_data = NarrationCompleted.model_validate(_data(draf))
    hasil = periksa(kode, draf_data.narasi, parse_items(json.loads(bukti.read_text(encoding="utf-8"))))
    kep = putuskan(kode, draf_data.narasi, hasil)
    ulang = perlu_ulang(hasil, draf_data.attempt)
    return {
        "status": "MINTA_ULANG" if ulang else kep.status,
        "percobaan": draf_data.attempt,
        "klaim_total": kep.klaim_total,
        "klaim_lolos": kep.klaim_lolos,
        "kegagalan": permintaan_ulang(hasil).model_dump(mode="json")["kegagalan"] if ulang else [],
        "evidence_set_hash": evidence_set_hash(kode),
        "klaim": [
            {"index": h.klaim.index, "jenis": h.klaim.jenis, "teks": h.klaim.teks, "kode_gagal": list(h.kode_gagal)}
            for h in hasil
        ],
        "model": {} if ulang else kep.model,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="astria-verifier-periksa", description=__doc__.splitlines()[0])
    parser.add_argument("--paket", type=Path, required=True)
    parser.add_argument("--draf", type=Path, required=True)
    parser.add_argument("--bukti", type=Path, required=True)
    args = parser.parse_args(argv)
    json.dump(run(args.paket, args.draf, args.bukti), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
