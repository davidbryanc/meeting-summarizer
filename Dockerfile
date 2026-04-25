FROM python:3.11-slim

# Install system dependencies termasuk ffmpeg untuk moviepy dan pydub
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements dulu untuk layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh project
COPY . .

# Buat folder yang dibutuhkan
RUN mkdir -p uploads outputs logs

# Pre-download pyannote model supaya user tidak nunggu saat pertama pakai
# Kalau HUGGINGFACE_TOKEN tidak diset, langkah ini dilewati tanpa error
ARG HUGGINGFACE_TOKEN
ENV HUGGINGFACE_TOKEN=$HUGGINGFACE_TOKEN
RUN python scripts/preload_models.py || echo "Pre-download skipped"