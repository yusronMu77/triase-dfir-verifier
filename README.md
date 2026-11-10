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
uv run python -m astria_verifier.cli --paket paket.json --draf draf.json --bukti bukti.json
```

## Cara kerja

| Bagian | Isi |
|---|---|
| `pipeline.py` | Paket dan draf disimpan di `paket_tunggu`/`draf_tunggu` sampai berpasangan (urutan bebas, kunci advisory per kartu); hasil per klaim ke `klaim_hasil`. Percobaan 1 dengan klaim gagal menerbitkan `narration.retry_requested` dan menunggu draf percobaan 2; hasil final ke `verifikasi`, lalu `card.verified` dan `audit.record` dalam satu transaksi |
| `checks.py` | Pemeriksaan per klaim, kode murni: `TANPA_BUKTI`, `ID_TIDAK_DITEMUKAN`, `BUKTI_BERUBAH`, `VALID_TAPI_SALAH`, `ENTITAS_TIDAK_BERDASAR`, `BERTENTANGAN_DENGAN_KODE`, `KODE_LANGKAH_ASING`, `PERAN_BERTENTANGAN`. Teknik ATT&CK dan temuan `K-...` dicocokkan ke `kode.teknik_attack` dan `kode.temuan_korelasi`. Skema ditegakkan model kontrak |
| `policy.py` | `LULUS` bila semua lolos (percobaan 1 atau 2); klaim gagal di percobaan 1 berarti minta ulang dengan kode gagal saja; di percobaan 2 `SEBAGIAN` bila lolos >= ambang (bawaan 0,70) dan klaim gagal dibuang, selain itu `TEMPLAT` dengan `dokumen.model` kosong |
| `evidence.py` | Bukti asli wajib dari ingest `POST /svc/v1/evidence:batch` dengan token layanan; ID yang belum ada dicoba sekali lagi, lalu klaim yang merujuknya gagal `ID_TIDAK_DITEMUKAN`. Ingest yang tidak terjangkau membuat event dikirim ulang |

Konfigurasi: `ASTRIA_VERIFIER_INGEST_URL` (bawaan `http://ingest:8000`; wajib bersama `ASTRIA_SERVICE_KEY`/`_FILE`),
`ASTRIA_VERIFIER_AMBANG_SEBAGIAN`. Selama endpoint bukti ingest (ingest#2) belum ada, kartu tidak bisa diperiksa: event dikirim ulang lalu masuk DLQ.
Verifier membuktikan keterlacakan, bukan kebenaran semantik; pengenalan nama akun dan host adalah heuristik. Belum ada batas tunggu
(`VER_PAKET_KEDALUWARSA`) untuk pasangan atau draf percobaan 2 yang tidak datang.

## Alur git

Branch `{type}/{yyyyMMdd}-{taskId}-{nama}`; commit `{type}({yyyyMMddHHmm}): [{taskId}] {pesan}`, satu baris, tanpa trailer. `main` hanya berubah lewat pull request (merge rebase); jangan push langsung ke `main` dan jangan `--no-verify`.
