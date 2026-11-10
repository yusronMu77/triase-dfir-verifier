import json
from pathlib import Path

from astria_contracts import example
from helpers import bukti_asli

from astria_verifier.cli import run


def _write(tmp_path: Path, name: str, data) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_cli_checks_contract_examples_deterministically(tmp_path: Path) -> None:
    paket = _write(tmp_path, "paket.json", example("card.skeleton.created"))
    draf = _write(tmp_path, "draf.json", example("narration.completed")["data"])
    items = [{"evidence_id": i, "record_sha256": b.sha256, "fields": dict(b.fields)} for i, b in bukti_asli().items()]
    bukti = _write(tmp_path, "bukti.json", {"items": items, "not_found": []})

    first = run(paket, draf, bukti)
    assert first == run(paket, draf, bukti)
    assert first["bukti_asli_dibaca"] is True
    # Tanpa teks host di bukti tiruan, WS-HR-11 tidak berdasar pada kode maupun bukti.
    assert first["klaim"][0]["kode_gagal"] == ["ENTITAS_TIDAK_BERDASAR"]
    assert first["status"] in {"SEBAGIAN", "TEMPLAT"}

    tanpa_bukti = run(paket, draf, None)
    assert tanpa_bukti["bukti_asli_dibaca"] is False
    assert "BUKTI_TIDAK_TERSEDIA" in tanpa_bukti["klaim"][0]["kode_gagal"]
