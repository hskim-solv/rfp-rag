FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY rfp_rag ./rfp_rag

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/artifacts \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD uv run --no-sync python -c "import json, os, urllib.request; port=os.getenv('PORT', '8000'); payload=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=2)); raise SystemExit(0 if payload.get('ok') is True and payload.get('service') == 'rfp-rag' else 1)"

CMD ["sh", "-c", "uv run --no-sync uvicorn rfp_rag.service.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
