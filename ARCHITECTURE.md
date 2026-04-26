# Architecture Decision Records

## Tech Stack Overview

| Layer | Technology | Alasan |
|---|---|---|
| UI | Chainlit | Native support streaming, file upload, session management — cocok untuk chat-based AI app |
| Speech-to-text | Groq Whisper Large V3 | Gratis, tercepat di kelasnya, support bahasa Indonesia |
| LLM | Gemini 2.0 Flash | Gratis tier yang generous, context window besar untuk transcript panjang |
| Diarization | pyannote 4.0 | State-of-the-art speaker diarization, open source |
| Export | fpdf2 | Lightweight, tidak butuh dependency eksternal seperti wkhtmltopdf |
| Logging | loguru | Lebih simpel dari standard logging, structured output, rotation otomatis |
| Deploy | Railway + Docker | Support Dockerfile langsung dari GitHub, free tier cukup untuk demo |

## Key Decisions

### 1. Groq over OpenAI Whisper API
Groq menyediakan Whisper Large V3 gratis dengan kecepatan jauh lebih tinggi
karena menggunakan LPU (Language Processing Unit). Untuk development dan demo,
ini jauh lebih cost-effective dibanding OpenAI API yang berbayar per menit.

### 2. Strategy pattern di TranscriberService
TranscriberService dirancang dengan provider pattern sehingga mudah ganti
backend (Groq → local Whisper → OpenAI) tanpa mengubah kode di layer lain.
Ini menerapkan Open/Closed Principle — open for extension, closed for modification.

### 3. Diarization sebagai fitur opsional
pyannote.audio membutuhkan torch ~2GB yang melebihi batas image Railway free tier (4GB).
Keputusan: pisahkan requirements.txt (production) dan requirements-local.txt (development).
Diarization tetap tersedia di local deployment dan dapat didemonstrasikan.
Di production, pipeline tetap berjalan penuh tanpa diarization.

### 4. Lazy loading pipeline pyannote
Model diarization (~1GB) hanya diload saat pertama kali dibutuhkan, bukan saat startup.
Ini menghindari delay startup yang panjang dan menghemat memory kalau fitur tidak dipakai.

### 5. Auto-cleanup file upload
File audio dihapus otomatis setelah transcribe selesai untuk mencegah storage penuh.
Yang disimpan permanen hanya transcript (.txt) dan summary (.md + .pdf) di folder outputs/.

### 6. On-demand export
Transcript dan summary tidak langsung dikirim sebagai file attachment karena
Chainlit 2.x mengubah cara kerja cl.File. Sebagai gantinya, user bisa ketik
"export transcript" atau "export summary" kapanpun untuk generate file.

### 7. Conversation memory dengan batas 20 pesan
Chat history disimpan di Chainlit session dan dikirim ke LLM setiap Q&A request.
Dibatasi 20 pesan terakhir untuk menghindari context window overflow pada
transcript yang panjang + history percakapan yang panjang secara bersamaan.

## Pipeline Flow
Upload file (mp3/mp4/wav/m4a)
→ Validasi format & ukuran
→ Extract audio (jika mp4, via moviepy)
→ Transcribe (Groq Whisper, auto-chunking jika > 10 menit)
→ Diarization opsional (pyannote, local only)
→ LLM summarization (Gemini 2.0 Flash, streaming)
→ Display summary + action items
→ Auto-save transcript & summary ke outputs/
→ Q&A mode aktif (user bisa tanya tentang isi meeting)

## Deployment Architecture
GitHub repo
→ Railway (auto-deploy on push)
→ Docker container (python:3.11-slim + ffmpeg)
→ Chainlit app (port 8000)
→ External APIs: Groq, Gemini, HuggingFace (local only)

## Known Limitations
- Diarization tidak tersedia di Railway free tier karena image size limit 4GB
- File output tersimpan di container Railway — hilang saat redeploy (tidak ada persistent storage di free tier)
- Tidak ada authentication — siapapun dengan URL bisa akses app
- Context window Gemini bisa penuh untuk meeting sangat panjang (> 2 jam)