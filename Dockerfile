FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install torch CPU-only dulu sebelum requirements lain
RUN pip install --no-cache-dir \
    torch==2.6.0+cpu \
    torchaudio==2.6.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install sisanya
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads outputs logs

ARG HUGGINGFACE_TOKEN
ENV HUGGINGFACE_TOKEN=$HUGGINGFACE_TOKEN
RUN python scripts/preload_models.py || echo "Pre-download skipped"

EXPOSE 8000

CMD ["chainlit", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]