# Meeting Summarizer AI

[![CI](https://github.com/davidbryanc/meeting-summarizer/actions/workflows/ci.yml/badge.svg)]
![CD](https://github.com/davidbryanc/meeting-summarizer/actions/workflows/cd.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)


Upload rekaman meeting (mp3, mp4, wav, m4a) dan dapatkan:
- Transcript lengkap otomatis
- Ringkasan meeting, topik, dan keputusan penting
- Action items dengan assignee dan prioritas
- Identifikasi pembicara (local deployment)
- Q&A interaktif tentang isi meeting
- Export transcript dan summary PDF

## Demo

🔗 **Live demo**: `https://meeting-summarizer-production-3223.up.railway.app/`
*(Aktif saat interview/demo — hubungi untuk jadwal)*

## Fitur Utama

### Pipeline otomatis end-to-end
Upload file → transcript → diarization → summary → action items, semua dalam satu flow tanpa konfigurasi tambahan.

### Async job processing
Setiap upload langsung return `job_id` — tidak ada blocking. Job diproses worker terpisah via Redis queue, UI polling status secara real-time.

### Speaker diarization dengan word-level alignment
WhisperX menghasilkan timestamp per kata, pyannote mengidentifikasi siapa yang bicara kapan. Setiap kata di-assign ke speaker yang tepat — bukan estimasi per kalimat.

### Q&A interaktif
Setelah summary muncul, tanya apapun tentang isi meeting:
- *"Siapa yang bertanggung jawab untuk X?"*
- *"Apa keputusan tentang budget?"*
- *"Ringkas poin yang dibahas SPEAKER_00"*

### Export on-demand
Ketik `export transcript` atau `export summary` untuk download file langsung dari chat.

### Auto language detection
Whisper Large V3 otomatis deteksi bahasa — support Indonesia, Inggris, dan 90+ bahasa lainnya tanpa konfigurasi.

## Tech Stack

| Layer | Technology | Alasan |
|---|---|---|
| UI | Chainlit | Native streaming, file upload, session management |
| API | FastAPI + uvicorn | Async REST endpoints, auto Swagger docs |
| Job Queue | ARQ + Redis | Non-blocking async processing |
| Speech-to-text | Groq Whisper Large V3 | Gratis, tercepat, support 90+ bahasa |
| Word alignment | WhisperX | Word-level timestamps untuk diarization akurat |
| Speaker ID | pyannote-audio 4.0 | State-of-the-art diarization |
| LLM | Gemini 2.5 Flash | Context window besar, gratis tier |
| Export | fpdf2 | Lightweight PDF tanpa system dependency |
| Logging | loguru | Structured logging dengan rotation otomatis |
| Deploy | Railway + Docker | Auto-deploy dari GitHub, free tier |
| CI/CD | GitHub Actions | Lint + test + Docker build otomatis |

## Arsitektur

```
┌─────────────┐     HTTP      ┌─────────────────┐
│   Chainlit  │ ────────────► │    FastAPI       │
│   (UI/Chat) │ ◄──polling─── │   :8001/docs     │
└─────────────┘               └────────┬────────┘
                                        │ enqueue
                                        ▼
                               ┌─────────────────┐
                               │   Redis Queue    │
                               └────────┬────────┘
                                        │ dequeue
                                        ▼
                               ┌─────────────────┐
                               │   ARQ Worker     │
                               │ Groq → WhisperX  │
                               │ → pyannote       │
                               └────────┬────────┘
                                        │
                              ┌─────────▼─────────┐
                              │   Gemini LLM       │
                              │ Summary + Q&A      │
                              └───────────────────┘
```

## Cara Run Lokal

### Prerequisites
- Python 3.11
- Docker Desktop (untuk Redis)
- API keys: Groq, Gemini, HuggingFace

### Setup

```bash
git clone https://github.com/davidbryanc/meeting-summarizer.git
cd meeting-summarizer

python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements-local.txt

cp .env.example .env          # isi API key
```

### Jalankan (4 terminal)

```bash
# Terminal 1 — Redis
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine

# Terminal 2 — FastAPI
uvicorn api.main:app --reload --port 8001

# Terminal 3 — ARQ Worker
python -m arq workers.transcribe_worker.WorkerSettings

# Terminal 4 — Chainlit UI
chainlit run app/main.py
```

Buka `http://localhost:8000`

### Atau dengan Docker Compose

```bash
docker-compose up --build
```

## Environment Variables

```env
GROQ_API_KEY=              # console.groq.com (gratis)
GEMINI_API_KEY=            # aistudio.google.com (gratis)
HUGGINGFACE_TOKEN=         # huggingface.co/settings/tokens
REDIS_URL=redis://localhost:6379
TRANSCRIPTION_PROVIDER=groq    # groq | whisperx
DIARIZATION_ENABLED=true
APP_ENV=development
MAX_FILE_SIZE_MB=100
```

## API Documentation

FastAPI auto-generate Swagger UI di `http://localhost:8001/docs`

Endpoints:
- `POST /transcribe` — upload audio, return `job_id`
- `GET /jobs/{job_id}` — poll status transcription job
- `POST /summarize` — summarize transcript
- `POST /summarize/stream` — streaming summarization via SSE
- `GET /download/{filename}` — download output file
- `GET /health` — health check

## Testing

```bash
pytest -v
```

22 unit tests covering:
- File validation dan audio processing
- Transcription service dengan mock provider
- LLM processor parsing dan streaming
- API endpoints dengan TestClient

## Struktur Project

```
meeting-summarizer/
├── app/main.py                  # Chainlit UI entry point
├── api/
│   ├── main.py                  # FastAPI app
│   └── routes/
│       ├── transcribe.py        # POST /transcribe
│       ├── summarize.py         # POST /summarize
│       ├── jobs.py              # GET /jobs/{job_id}
│       └── download.py          # GET /download/{filename}
├── workers/
│   └── transcribe_worker.py     # ARQ background worker
├── services/
│   ├── file_handler.py          # Upload, validasi, audio extraction
│   ├── transcriber.py           # Provider pattern: Groq | WhisperX
│   ├── whisperx_transcriber.py  # Word-level timestamps
│   ├── diarizer.py              # pyannote speaker diarization
│   └── llm_processor.py        # Gemini summarization + Q&A streaming
├── models/
│   ├── schemas.py               # Pydantic domain models
│   └── api_schemas.py           # API request/response models
├── config/settings.py           # Centralized config via Pydantic
├── utils/
│   ├── audio_utils.py           # Audio processing helpers
│   ├── export.py                # PDF & txt export
│   ├── eta.py                   # ETA estimation
│   ├── logger.py                # Structured logging
│   └── prompt_utils.py          # Prompt template loader
├── prompts/
│   ├── summarize.txt            # LLM prompt untuk summary
│   └── qa.txt                   # LLM prompt untuk Q&A
├── tests/                       # 22 pytest unit tests
├── .github/workflows/           # CI/CD GitHub Actions
├── Dockerfile
├── docker-compose.yml
└── ARCHITECTURE.md
```

## Progress

### Initial Build (10 hari)
- [x] Day 1 — Project structure & Chainlit setup
- [x] Day 2 — Audio/video ingestion pipeline
- [x] Day 3 — Speech-to-text dengan Groq Whisper
- [x] Day 4 — LLM summarization dengan streaming
- [x] Day 5 — UI polish & export
- [x] Day 6 — Speaker diarization & auto language detection
- [x] Day 7 — Q&A mode dengan conversation memory
- [x] Day 8 — Structured logging & PDF export
- [x] Day 9 — Docker & Railway production deploy
- [x] Day 10 — Documentation & portfolio ready

### Upgrade (5 hari)
- [x] Day 1 — FastAPI backend + async job endpoints + Swagger
- [x] Day 2 — WhisperX word-level alignment untuk diarization akurat
- [x] Day 3 — cl.Step progress, ETA estimation, file download via API
- [x] Day 4 — ARQ + Redis async job queue + concurrent processing
- [x] Day 5 — 22 pytest unit tests + GitHub Actions CI/CD