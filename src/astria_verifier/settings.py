"""Konfigurasi verifier dari env `ASTRIA_*`. Tambahkan field milik layanan ini di sini."""

from astria_common.settings import AstriaSettings


class Settings(AstriaSettings):
    service_name: str = "verifier"
