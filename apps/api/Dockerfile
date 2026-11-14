# One image for the API, the Celery worker and the scheduler. The start command picks the role:
#   API:       the default CMD below
#   worker:    celery -A app.celery_app worker --loglevel=info --concurrency=2
#   scheduler: celery -A app.celery_app beat --loglevel=info
# Build from apps/api: docker build -t careerfit-api .
FROM python:3.12-slim-bookworm

# Tesseract reads scanned resumes (English and Russian).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed \
    PORT=8000

RUN useradd --create-home --uid 10001 careerfit
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY data ./data
COPY scripts ./scripts
RUN uv sync --frozen --no-dev

# Bake the embedding model into the image, so containers don't download it on every start.
RUN python -c "from fastembed import TextEmbedding; from app.embeddings import MODEL_NAME; TextEmbedding(MODEL_NAME)" \
    && chown -R careerfit /app/.cache

USER careerfit
EXPOSE 8000

# The host's proxy (Railway or Render) is the only way in, so its forwarded address is trusted: rate
# limits then count visitors, not the proxy.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
