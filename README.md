# Meeting Summarizer AI

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

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Chainlit |
| Speech-to-text | Groq Whisper Large V3 |
| LLM | Gemini 2.5 Flash |
| Speaker diarization | pyannote-audio 4.0 |
| Deploy | Railway + Docker |

## Cara Run Lokal

```bash
git clone https://github.com/username/meeting-summarizer.git
cd meeting-summarizer
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements-local.txt
cp .env.example .env          # isi API key
chainlit run app/main.py
```

Buka `http://localhost:8000`

## Environment Variables

```env
GROQ_API_KEY=         # console.groq.com (gratis)
GEMINI_API_KEY=       # aistudio.google.com (gratis)
HUGGINGFACE_TOKEN=    # huggingface.co/settings/tokens (untuk diarization)
```

## Fitur

### Pipeline otomatis
Upload file → transcript → summary → action items, semua dalam satu flow.

### Speaker diarization (local)
Identifikasi siapa yang bicara apa menggunakan pyannote-audio.
Tersedia di local deployment, dinonaktifkan di production karena resource constraint.

### Q&A interaktif
Setelah summary muncul, tanya apapun tentang isi meeting:
- *"Siapa yang bertanggung jawab untuk X?"*
- *"Apa keputusan tentang Y?"*
- *"Ringkas poin yang dibahas oleh speaker 1"*

### Export on-demand
Ketik `export transcript` atau `export summary` untuk download file.

## Struktur Project

```
meeting-summarizer/
├── app/main.py              # Chainlit entry point
├── services/
│   ├── file_handler.py      # Upload, validasi, audio extraction
│   ├── transcriber.py       # Groq Whisper wrapper + chunking
│   ├── diarizer.py          # pyannote speaker diarization
│   └── llm_processor.py     # Gemini summarization + Q&A
├── models/schemas.py        # Pydantic models
├── config/settings.py       # Centralized configuration
├── utils/
│   ├── audio_utils.py       # Audio processing helpers
│   ├── export.py            # PDF & txt export
│   └── logger.py            # Structured logging
├── prompts/                 # LLM prompt templates
├── Dockerfile
├── docker-compose.yml
└── ARCHITECTURE.md
```

## Progress

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