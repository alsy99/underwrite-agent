FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY packages packages
COPY apps apps
COPY scripts scripts
COPY data data

RUN pip install --no-cache-dir -e ".[dev]"

ENV PYTHONPATH=/app
