"""Jalankan layanan: `astria-verifier` atau `python -m astria_verifier`."""

from astria_common.app import run

from astria_verifier.main import build_app
from astria_verifier.settings import Settings


def main() -> None:
    settings = Settings()
    run(build_app(settings), settings)


if __name__ == "__main__":
    main()
