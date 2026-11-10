<!-- astria-logo -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/astria-logo-reverse.svg">
    <img src=".github/assets/astria-logo.svg" alt="Astria" width="320">
  </picture>
</p>

# Astria verifier

Memeriksa klaim narasi terhadap bukti sebelum kartu terbit.

> Status: Tahap 1 (verifier#2). Memasangkan `card.skeleton.created` dan `narration.completed`, memeriksa setiap klaim, lalu menerbitkan `card.verified` dan `audit.record` lewat outbox. Repo ini adalah submodule dari workspace `triase-dfir` (folder `verifier/`). Rancangan: `notes/2026-11-06-triase-dfir-app-verifier.md` di repo root. Lajur developer: 2.

## Tech stack

Python 3.14, FastAPI, NATS JetStream, uv

## Perintah

```text
uv sync                                   # butuh akses ke repo privat contracts dan common (tag git)
uv run ruff format --check . && uv run ruff check .
uv run pytest
sh ../common/template/localtest.sh        # di kontainer py devenv: uji terhadap salinan kerja common dan contracts
```

Menjalankan bersama layanan lain: `pwsh ../devenv/scripts/dev.ps1 up`, lalu `dev.ps1 smoke`.

Uji integrasi (`tests/test_integration.py`) butuh `ASTRIA_TEST_DATABASE_URL`; di kontainer `py` devenv isi dengan
`postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:5432/postgres`. Tanpa variabel itu uji tersebut dilewati.

Periksa satu draf tanpa NATS dan basis data (untuk eval):

```text
uv run python -m astria_verifier.cli --paket paket.json --draf draf.json [--bukti bukti.json]
```

## Cara kerja

| Bagian | Isi |
|---|---|
| `pipeline.py` | Paket dan draf disimpan di `paket_tunggu`/`draf_tunggu` sampai berpasangan (urutan bebas, kunci advisory per kartu); hasil ke `verifikasi` dan `klaim_hasil`, lalu `card.verified` dan `audit.record` dalam satu transaksi |
| `checks.py` | Pemeriksaan per klaim, kode murni: `TANPA_BUKTI`, `ID_TIDAK_DITEMUKAN`, `BUKTI_BERUBAH`, `VALID_TAPI_SALAH`, `BUKTI_TIDAK_TERSEDIA`, `ENTITAS_TIDAK_BERDASAR`, `BERTENTANGAN_DENGAN_KODE`, `KODE_LANGKAH_ASING`, `PERAN_BERTENTANGAN`. Skema ditegakkan model kontrak |
| `policy.py` | `LULUS` bila semua lolos; `SEBAGIAN` bila lolos >= ambang (bawaan 0,70), klaim gagal dibuang; selain itu `TEMPLAT` dengan `dokumen.model` kosong |
| `evidence.py` | Bukti asli dari ingest `POST /svc/v1/evidence:batch` dengan token layanan |

Konfigurasi: `ASTRIA_VERIFIER_INGEST_URL` (kosong = bukti asli tidak dibaca; pemeriksaan memakai `kode` saja dan klaim yang mengutip nilai gagal
`BUKTI_TIDAK_TERSEDIA`), `ASTRIA_VERIFIER_AMBANG_SEBAGIAN`. Verifier membuktikan keterlacakan, bukan kebenaran semantik; pengenalan nama akun
dan host adalah heuristik. Tahap 1 hanya satu percobaan karena `narration.retry_requested` belum ada di kontrak.

## Alur git

Branch `{type}/{yyyyMMdd}-{taskId}-{nama}`; commit `{type}({yyyyMMddHHmm}): [{taskId}] {pesan}`, satu baris, tanpa trailer. `main` hanya berubah lewat pull request (merge rebase); jangan push langsung ke `main` dan jangan `--no-verify`.
