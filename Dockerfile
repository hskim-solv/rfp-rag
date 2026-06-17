FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY rfp_rag ./rfp_rag

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "rfp_rag.service.app:app", "--host", "0.0.0.0", "--port", "8000"]
