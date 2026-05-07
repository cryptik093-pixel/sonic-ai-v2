FROM python:3.12-slim
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy backend sources
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN pip install --upgrade pip
# If you use poetry, adjust accordingly. Here we fallback to pip requirements if present.
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

COPY backend/ ./backend/
WORKDIR /app/backend

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "-b", "0.0.0.0:8080"]
