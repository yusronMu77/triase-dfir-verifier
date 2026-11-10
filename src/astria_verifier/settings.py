"""Konfigurasi verifier dari env `ASTRIA_*`."""

from astria_common.settings import AstriaSettings

from astria_verifier.policy import AMBANG_SEBAGIAN


class Settings(AstriaSettings):
    service_name: str = "verifier"

    verifier_ingest_url: str | None = None
    """Basis URL ingest untuk membaca bukti asli (ASTRIA_VERIFIER_INGEST_URL), mis. http://ingest:8000.
    Kosong = bukti asli tidak dibaca: pemeriksaan memakai kode kartu saja, dan klaim yang mengutip nilai gagal
    `BUKTI_TIDAK_TERSEDIA`. Endpoint ingest `POST /svc/v1/evidence:batch` dibangun di ingest#2."""
    verifier_ambang_sebagian: float = AMBANG_SEBAGIAN
    """Persentase klaim lolos minimal untuk SEBAGIAN (contoh dari rancangan, belum dikalibrasi)."""
