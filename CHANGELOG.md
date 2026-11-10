# Changelog

## [Unreleased]

### Added

- verifier#2: pemasangan paket dan draf, pemeriksaan klaim terhadap kode kartu dan bukti asli ingest (opsional), kebijakan LULUS/SEBAGIAN/TEMPLAT, `card.verified` dan `audit.record` lewat outbox, tabel `verifikasi` dan `klaim_hasil`, dan CLI `python -m astria_verifier.cli`.
- Kerangka layanan Tahap 0 dari templat `common` v0.1.0: `/health`, `/ready`, `/metrics`, token layanan, Dockerfile non-root, CI (lint, uji, gitleaks, build image, smoke `/ready`).
- Logo Astria di kepala README (`.github/assets/`, dari kit logo di repo `triase-dfir-uiux`).
