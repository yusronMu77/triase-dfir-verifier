<!-- astria-logo -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/astria-logo-reverse.svg">
    <img src=".github/assets/astria-logo.svg" alt="Astria" width="320">
  </picture>
</p>

# Astria verifier

Memeriksa klaim narasi terhadap bukti sebelum kartu terbit.

> Status: Tahap 0, kerangka layanan dari templat `common` v0.1.0 (`/health`, `/ready`, `/metrics`, token layanan, Dockerfile, CI). Repo ini adalah submodule dari workspace `triase-dfir` (folder `verifier/`). Rancangan: `notes/2026-11-06-triase-dfir-app-verifier.md` di repo root. Lajur developer: 2.

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

## Alur git

Branch `{type}/{yyyyMMdd}-{taskId}-{nama}`; commit `{type}({yyyyMMddHHmm}): [{taskId}] {pesan}`, satu baris, tanpa trailer. `main` hanya berubah lewat pull request (merge rebase); jangan push langsung ke `main` dan jangan `--no-verify`.
