"""Rakit aplikasi verifier: komponen standar (PostgreSQL, NATS, relay outbox) dan router.

Dev memakai `uvicorn astria_verifier.main:build_app --factory --reload`; image memakai `astria-verifier`.
"""

from astria_common.app import create_app
from astria_common.service import standard_runtime
from fastapi import FastAPI

from astria_verifier import api
from astria_verifier.settings import Settings


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    runtime = standard_runtime(settings)
    # Tambahkan konsumen event di sini, mis.:
    # runtime.add(Consumer(runtime.require_bus(), runtime.require_db(),
    #                      durable="verifier", event_type="...", handler=...))
    return create_app(settings, components=runtime.components, routers=[api.router])
