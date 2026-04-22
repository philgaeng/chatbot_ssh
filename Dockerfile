FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.grm.txt /app/
RUN pip install --upgrade pip \
    && pip install -r /app/requirements.txt \
    && pip install -r /app/requirements.grm.txt

COPY . /app

