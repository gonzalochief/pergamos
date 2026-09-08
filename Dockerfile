# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

COPY . /app

RUN python -m pip install --upgrade pip && \
    python -m pip install --prefix=/install -e '.[rag]'

FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

COPY --from=builder /install /usr/local
COPY --from=builder /app/src /app/src
COPY --from=builder /app/tests /app/tests

USER nonroot:nonroot

ENTRYPOINT ["/usr/bin/python3", "-m", "pergamos.server"]
