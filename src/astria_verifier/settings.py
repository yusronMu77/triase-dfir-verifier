"""Konfigurasi verifier dari env `ASTRIA_*`."""

from astria_common.settings import AstriaSettings

from astria_verifier.policy import AMBANG_SEBAGIAN


class Settings(AstriaSettings):
    service_name: str = "verifier"

    verifier_ingest_url: str = "http://ingest:8000"
    """Basis URL ingest untuk membaca bukti asli (ASTRIA_VERIFIER_INGEST_URL). Wajib: tanpa bukti asli kartu
    tidak diperiksa. Endpoint `POST /svc/v1/evidence:batch` dibangun di ingest#2."""
    verifier_ambang_sebagian: float = AMBANG_SEBAGIAN
    """Persentase klaim lolos minimal untuk SEBAGIAN (contoh dari rancangan, belum dikalibrasi)."""
