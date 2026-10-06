FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////app/data/cache.db

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
