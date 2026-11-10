"""Rakit aplikasi verifier: komponen standar, konsumen paket dan draf, dan router.

Dev memakai `uvicorn astria_verifier.main:build_app --factory --reload`; image memakai `astria-verifier`.
"""

from astria_common.app import create_app
from astria_common.auth import ServiceTokenClient
from astria_common.consumer import Consumer
from astria_common.service import standard_runtime
from fastapi import FastAPI

from astria_verifier import api
from astria_verifier.evidence import IngestEvidence
from astria_verifier.pipeline import Verifier, metadata
from astria_verifier.settings import Settings


def _evidence(settings: Settings) -> IngestEvidence | None:
    if settings.verifier_ingest_url is None:
        return None
    key = settings.service_key_bytes()
    if key is None:
        raise RuntimeError("verifier: ASTRIA_SERVICE_KEY atau _FILE wajib untuk membaca bukti dari ingest")
    tokens = ServiceTokenClient(settings.service_name, key, settings.identity_url)
    return IngestEvidence(tokens, settings.verifier_ingest_url)


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    runtime = standard_runtime(settings, metadata=[metadata])
    if runtime.db is not None and runtime.bus is not None:
        verifier = Verifier(_evidence(settings), ambang=settings.verifier_ambang_sebagian)
        for durable, event_type, handler in (
            ("verifier-paket", "card.skeleton.created", verifier.on_paket),
            ("verifier-draf", "narration.completed", verifier.on_draf),
        ):
            runtime.add(Consumer(runtime.bus, runtime.db, durable=durable, event_type=event_type, handler=handler))
    return create_app(settings, components=runtime.components, routers=[api.router])
