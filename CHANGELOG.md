# Changelog

## [Unreleased]

### Changed

- Sesuai rancangan (note app-verifier 5.1, 5.2, 5.6, 5.7): bukti asli dari ingest wajib (ID yang hilang dicoba sekali lagi, lalu `ID_TIDAK_DITEMUKAN`); kode `BUKTI_TIDAK_TERSEDIA` dan kolom `verifikasi.bukti_asli_dibaca` dihapus; klaim gagal di percobaan 1 menerbitkan `narration.retry_requested` dan status diputuskan di percobaan 2; teknik dan temuan dicocokkan ke `kode.teknik_attack` dan `kode.temuan_korelasi`. `--bukti` di CLI wajib. Kebijakan `verifikasi-1.1.0`, pemeriksa `verifier-0.2.0`. Butuh `astria-contracts` v0.2.0. Kolom baru `paket_tunggu.diminta_ulang_pada` menandai percobaan 2 sudah diminta. Basis data dev yang sudah ada: `ALTER TABLE verifikasi DROP COLUMN bukti_asli_dibaca` dan `ALTER TABLE paket_tunggu ADD COLUMN diminta_ulang_pada timestamptz` (belum ada Alembic).

### Added

- verifier#2: pemasangan paket dan draf, pemeriksaan klaim terhadap kode kartu dan bukti asli ingest (opsional), kebijakan LULUS/SEBAGIAN/TEMPLAT, `card.verified` dan `audit.record` lewat outbox, tabel `verifikasi` dan `klaim_hasil`, dan CLI `python -m astria_verifier.cli`.
- Kerangka layanan Tahap 0 dari templat `common` v0.1.0: `/health`, `/ready`, `/metrics`, token layanan, Dockerfile non-root, CI (lint, uji, gitleaks, build image, smoke `/ready`).
- Logo Astria di kepala README (`.github/assets/`, dari kit logo di repo `triase-dfir-uiux`).
