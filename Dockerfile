# syntax=docker/dockerfile:1
# Build dependencies without copying local credentials or the host virtualenv.
FROM python:3.11-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python
# Fetch the tokenizer vocabulary at build time, never the provider credentials.
RUN .venv/bin/python -c "import tiktoken; tiktoken.encoding_for_model('gpt-4o-mini')" \
    && chmod -R a+rX /opt/tiktoken-cache

FROM python:3.11-slim-bookworm AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache
RUN groupadd --gid 10001 gateway \
    && useradd --uid 10001 --gid 10001 --create-home gateway
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /opt/tiktoken-cache /opt/tiktoken-cache
COPY src ./src
USER 10001:10001
EXPOSE 8000
# Local readiness check only: no API call, credentials or provider charges.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/models', timeout=2).close()"]
CMD ["python", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
