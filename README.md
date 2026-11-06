# Astria verifier

Memeriksa klaim narasi terhadap bukti sebelum kartu terbit.

> Status: kerangka awal, belum ada kode. Repo ini adalah submodule dari workspace `triase-dfir` (folder `verifier/`). Rancangan: `notes/2026-11-06-triase-dfir-app-verifier.md` di repo root. Lajur developer: 2.

## Tech stack

Python 3.14, FastAPI, NATS JetStream, uv

## Perintah

```text
uv sync
uv run pytest
```

## Alur git

Branch `{type}/{yyyyMMdd}-{taskId}-{nama}`; commit `{type}({yyyyMMddHHmm}): [{taskId}] {pesan}`, satu baris, tanpa trailer. `main` hanya berubah lewat pull request (merge rebase); jangan push langsung ke `main` dan jangan `--no-verify`.
