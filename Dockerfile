FROM python:3.11-slim

# Railway force rebuild - v2
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir \
    torch==2.6.0+cpu \
    torchaudio==2.6.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads outputs logs

EXPOSE 8000

CMD ["chainlit", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]