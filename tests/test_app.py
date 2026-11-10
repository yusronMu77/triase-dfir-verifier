import pytest
from astria_common.envguard import EnvironmentGuardError
from fastapi.testclient import TestClient
from pydantic import SecretStr

from astria_verifier.main import build_app
from astria_verifier.settings import Settings


def test_health_and_ready_without_dependencies() -> None:
    with TestClient(build_app(Settings(env="test"))) as client:
        health = client.get("/health").json()
        assert health["service"] == "verifier"
        assert health["env"] == "test"
        assert client.get("/ready").status_code == 200
        assert "astria_service_info" in client.get("/metrics").text


DEV_DB = SecretStr("postgresql+psycopg://u:p@postgres:5432/verifier_dev")


def test_both_consumers_are_wired_when_db_and_nats_configured() -> None:
    app = build_app(Settings(env="dev", database_url=DEV_DB, nats_url="nats://nats:4222"))
    assert {"consumer:verifier-paket", "consumer:verifier-draf"} <= set(app.state.components)


def test_ingest_url_requires_service_key() -> None:
    settings = Settings(
        env="dev", database_url=DEV_DB, nats_url="nats://n:4222", verifier_ingest_url="http://ingest:8000"
    )
    with pytest.raises(RuntimeError):
        build_app(settings)
    build_app(settings.model_copy(update={"service_key": SecretStr("ab" * 32)}))


def test_refuses_to_start_with_non_dev_database_in_dev() -> None:
    url = SecretStr("postgresql+psycopg://u:p@postgres:5432/astria")
    with pytest.raises(EnvironmentGuardError):
        build_app(Settings(env="dev", database_url=url))
