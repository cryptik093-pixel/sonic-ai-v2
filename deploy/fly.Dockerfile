FROM python:3.12-slim
WORKDIR /app

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -e ./backend
WORKDIR /app/backend

ENV SONIC_AI_ENVIRONMENT=production
ENV SONIC_AI_MAX_UPLOAD_BYTES=209715200
ENV PORT=8080

CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker app.main:app -b 0.0.0.0:${PORT:-8080}"]
