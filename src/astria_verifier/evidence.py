"""Bukti asli dari ingest: `POST /svc/v1/evidence:batch` (note app-ingest 3.2), berkunci token layanan.

ID yang tidak dikembalikan ingest (`not_found`) tidak ada di hasil; pemeriksaan menandai klaimnya
`ID_TIDAK_DITEMUKAN`. Kegagalan jaringan dilempar agar konsumen mencoba ulang lalu ke DLQ.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from astria_common.auth import ServiceTokenClient
from astria_common.http import make_client

from astria_verifier.checks import Bukti

BATCH_PATH = "/svc/v1/evidence:batch"
_EVENT_DARI_KIND = re.compile(r"\.(\d{3,5})$")


def parse_items(payload: Mapping[str, Any]) -> dict[str, Bukti]:
    """Jawaban ingest `{items: [...], not_found: [...]}` menjadi peta ID ke Bukti."""
    hasil: dict[str, Bukti] = {}
    for item in payload.get("items", []):
        teks = [str(item[k]) for k in ("host", "account", "excerpt") if item.get(k)]
        if m := _EVENT_DARI_KIND.search(str(item.get("kind", ""))):
            teks.append(f"EventID={m.group(1)}")
        hasil[item["evidence_id"]] = Bukti(
            sha256=item["record_sha256"],
            fields={str(k): str(v) for k, v in (item.get("fields") or {}).items()},
            teks=tuple(teks),
        )
    return hasil


class IngestEvidence:
    def __init__(self, tokens: ServiceTokenClient, base_url: str) -> None:
        self._tokens = tokens
        self._http = make_client(base_url)

    async def fetch(self, ids: Sequence[str]) -> dict[str, Bukti]:
        headers = await self._tokens.auth_headers("svc:ingest")
        resp = await self._http.post(BATCH_PATH, json={"ids": sorted(set(ids))}, headers=headers)
        resp.raise_for_status()
        return parse_items(resp.json())
