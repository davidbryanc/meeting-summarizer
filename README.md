# Meeting Summarizer AI

Upload rekaman meeting (mp3, mp4, wav, m4a), dapatkan:
- Transcript lengkap otomatis
- Summary dalam bahasa Indonesia maupun Inggris
- Topik yang dibahas
- Key decisions & action items dengan prioritas

## Tech Stack
- **UI**: Chainlit
- **Speech-to-text**: Whisper Large V3 via Groq API
- **LLM**: Gemini 2.0 Flash (google-genai)
- **Deploy**: Railway (coming soon)

## Cara run lokal
````bash
git clone 
cd meeting-summarizer
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env         # isi API key kamu
chainlit run app/main.py
\```

## Environment variables
```env
GROQ_API_KEY=        # dari console.groq.com
GEMINI_API_KEY=      # dari aistudio.google.com
\```

## Status
- [x] Day 1 — Project structure & Chainlit setup
- [x] Day 2 — Audio/video ingestion pipeline
- [x] Day 3 — Speech-to-text dengan Groq Whisper
- [x] Day 4 — LLM summarization dengan streaming
- [ ] Day 5 — Chainlit UI polish & end-to-end integration
- [ ] Day 6 — Speaker diarization
- [ ] Day 7 — Q&A mode
- [ ] Day 8 — Logging & export
- [ ] Day 9 — Docker & Railway deploy
- [ ] Day 10 — Documentation & portfolio
```