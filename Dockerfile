# syntax=docker/dockerfile:1.10
# Dikelola template astria-common (template/service). Ubah di template, lalu render ulang.
ARG PYTHON_IMAGE=python:3.14.10-slim-bookworm

FROM ${PYTHON_IMAGE} AS build
ARG UV_VERSION=0.13.7
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "uv==${UV_VERSION}"
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
COPY pyproject.toml uv.lock ./
# astria-common dan astria-contracts adalah repo privat (tag git). Token build hanya ada selama langkah
# RUN ini (BuildKit secret `gh_token`) dan tidak masuk layer image maupun konfigurasi git.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=gh_token,env=GH_TOKEN \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="url.https://x-access-token:${GH_TOKEN}@github.com/yusronMu77/.insteadOf" \
    GIT_CONFIG_VALUE_0="https://github.com/yusronMu77/" \
    uv sync --locked --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=gh_token,env=GH_TOKEN \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0="url.https://x-access-token:${GH_TOKEN}@github.com/yusronMu77/.insteadOf" \
    GIT_CONFIG_VALUE_0="https://github.com/yusronMu77/" \
    uv sync --locked --no-dev --no-editable

FROM ${PYTHON_IMAGE} AS runtime
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin astria \
    && install -d -o astria -g astria -m 0700 /var/lib/astria/verifier
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"]
CMD ["astria-verifier"]
