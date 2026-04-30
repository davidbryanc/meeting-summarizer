# Architecture Decision Records

## System Overview

Meeting Summarizer adalah AI pipeline yang memproses audio/video rekaman meeting
menjadi transcript, summary, dan action items. Sistem dirancang dengan separation
of concerns yang jelas: UI layer (Chainlit), API layer (FastAPI), job processing
(ARQ + Redis), dan AI services (Groq, WhisperX, pyannote, Gemini).

## Architecture Diagram

```
Chainlit UI  ──HTTP──►  FastAPI API  ──enqueue──►  Redis Queue
     ▲                      │                           │
     │                      │                      ARQ Worker
     └──────polling──────────┘                          │
                                              ┌─────────┼─────────┐
                                              ▼         ▼         ▼
                                            Groq    WhisperX  pyannote
                                              └─────────┼─────────┘
                                                        ▼
                                                   Gemini LLM
                                                        │
                                                   outputs/
```

## Key Decisions

### 1. FastAPI sebagai API layer terpisah dari Chainlit
**Keputusan:** Business logic dipindah ke FastAPI, Chainlit hanya sebagai UI.

**Alasan:** Chainlit dirancang sebagai UI framework, bukan application server.
Dengan memisahkan keduanya, API bisa dikonsumsi oleh client lain (mobile app,
web app, third-party integration) tanpa bergantung pada Chainlit. FastAPI juga
menghasilkan Swagger documentation otomatis yang memudahkan testing dan onboarding.

**Trade-off:** Complexity bertambah — perlu jalankan dua process (Chainlit + FastAPI).
Dijustifikasi karena separation of concerns yang lebih clean dan extensibility jangka panjang.

### 2. ARQ + Redis untuk job queue, bukan FastAPI BackgroundTasks
**Keputusan:** Transcription job diproses oleh ARQ worker yang terpisah dari FastAPI process.

**Alasan:** FastAPI `BackgroundTasks` berjalan di thread pool yang sama dengan
HTTP server. Untuk operasi berat seperti transcription (~5-30 detik) dan diarization
(bisa menit), ini berisiko menghabiskan thread pool dan memblokir request lain.
ARQ menjalankan worker sebagai process terpisah — FastAPI tidak terpengaruh sama sekali.

**Trade-off:** Butuh Redis sebagai message broker. Dijustifikasi karena Redis
juga dipakai sebagai job store, sehingga tidak ada dependency tambahan yang sia-sia.
Untuk concurrent users, ARQ jauh lebih scalable.

### 3. Groq untuk transcription, WhisperX untuk alignment
**Keputusan:** Transcription teks menggunakan Groq API, WhisperX hanya untuk
word-level timestamp alignment saat diarization diaktifkan.

**Alasan:** Groq menjalankan Whisper Large V3 di LPU (Language Processing Unit)
yang menghasilkan transcription 5-10x lebih cepat dari CPU lokal.
WhisperX di CPU lokal butuh 2-5 menit untuk audio 10 menit — tidak acceptable
sebagai primary transcription path.

Dengan memisahkan peran keduanya, kita dapat kecepatan Groq + akurasi diarization
WhisperX. WhisperX hanya dijalankan saat diarization diperlukan, bukan setiap request.

**Trade-off:** Dua model dijalankan untuk pipeline diarization penuh.
Di production dengan GPU, WhisperX bisa menggantikan Groq sepenuhnya
karena akan sama cepatnya dengan akurasi lebih tinggi.

### 4. pyannote-audio untuk speaker diarization
**Keputusan:** Menggunakan pyannote/speaker-diarization-3.1 untuk identifikasi speaker.

**Alasan:** pyannote adalah state-of-the-art dalam speaker diarization,
dengan DER (Diarization Error Rate) terendah di kelasnya untuk model open-source.
Alternatif seperti SpeechBrain memiliki akurasi lebih rendah.

**Trade-off:** Model besar (~1GB), butuh HuggingFace token, dan lambat di CPU.
Di production deployment (Railway free tier), diarization dinonaktifkan karena
image size limit 4GB. Tersedia penuh di local deployment.

### 5. Strategy pattern untuk TranscriberService
**Keputusan:** TranscriberService menggunakan provider pattern —
`groq`, `whisperx`, atau `local` bisa dipilih via environment variable.

**Alasan:** Menerapkan Open/Closed Principle. Menambah provider baru
(misalnya AssemblyAI, Deepgram) tidak memerlukan perubahan di layer lain —
cukup tambah method `_transcribe_newprovider()` dan register di `transcribe()`.
Chainlit dan FastAPI tidak perlu tahu provider apa yang dipakai.

### 6. In-memory job store → Redis job store
**Keputusan:** Job status disimpan di Redis, bukan Python dict in-memory.

**Alasan:** In-memory store hilang saat process restart dan tidak bisa
diakses oleh multiple process (FastAPI + ARQ worker adalah process terpisah).
Redis sebagai shared state memungkinkan FastAPI membuat job, ARQ worker
mengupdate status, dan Chainlit polling status — semua dari process berbeda
tanpa race condition.

**Trade-off:** Butuh Redis running. Dijustifikasi karena Redis sudah diperlukan
untuk ARQ queue, jadi tidak ada dependency tambahan.

### 7. Lazy loading untuk pyannote dan WhisperX
**Keputusan:** Model AI tidak diload saat startup, melainkan saat pertama kali dipanggil.

**Alasan:** Loading pyannote pipeline memakan waktu ~15 detik dan ~1GB memory.
Jika diload saat startup, setiap restart app akan delay 15 detik meski
diarization tidak digunakan. Lazy loading memastikan model hanya diload
saat benar-benar dibutuhkan, dan setelah itu di-cache di memory untuk request berikutnya.

### 8. Pemisahan requirements.txt dan requirements-local.txt
**Keputusan:** Production menggunakan `requirements.txt` tanpa pyannote dan torch.
Development lokal menggunakan `requirements-local.txt` yang extend requirements.txt.

**Alasan:** pyannote + torch menghasilkan Docker image ~6.5GB yang melebihi
Railway free tier limit 4GB. Dengan memisahkan requirements, production image
turun ke ~2GB. Diarization tetap tersedia di local deployment dan dapat
didemonstrasikan saat interview.

**Pattern ini umum di industri** — production dependencies berbeda dari
development dependencies, terutama untuk ML projects dengan model besar.

### 9. Ruff sebagai linter, bukan flake8 atau pylint
**Keputusan:** Menggunakan ruff untuk linting dan formatting.

**Alasan:** Ruff ditulis dalam Rust — 10-100x lebih cepat dari flake8.
Menggabungkan fungsi flake8, isort, dan sebagian pylint dalam satu tool.
Semakin banyak project besar (FastAPI, Pydantic, Hugging Face) yang migrasi ke ruff.
Untuk CI pipeline, kecepatan lint yang cepat mengurangi waktu tunggu developer.

### 10. Auto-cleanup file upload setelah processing
**Keputusan:** File audio dihapus otomatis setelah transcription selesai.

**Alasan:** File audio bisa besar (100MB-500MB). Menyimpan permanen akan
menghabiskan storage dengan cepat, terutama di cloud deployment dengan
storage terbatas. Yang perlu disimpan permanen hanya output teks (transcript,
summary) yang ukurannya jauh lebih kecil. TTL 1 jam di Redis memastikan
job metadata juga dibersihkan otomatis.

## Known Limitations & Future Work

| Limitation | Root Cause | Possible Solution |
|---|---|---|
| Diarization tidak tersedia di Railway | Image size limit 4GB | GPU cloud (RunPod, Modal) |
| WhisperX lambat di CPU | CPU inference | GPU deployment |
| Alignment bahasa Indonesia kurang akurat | wav2vec2 model terbatas | Fine-tune model lokal |
| Tidak ada auth | Scope project | Add Clerk atau Auth0 |
| Output files hilang saat Railway redeploy | No persistent storage | Railway Volume atau S3 |
| In-memory job store reset saat restart | Process lifecycle | Sudah solved dengan Redis |

## Technology Alternatives Considered

| Category | Chosen | Alternatives Considered | Reason Not Chosen |
|---|---|---|---|
| UI | Chainlit | Gradio, Streamlit | Chainlit punya native streaming dan session management yang lebih baik untuk chat |
| API | FastAPI | Flask, Django | FastAPI async-native dan auto Swagger, Flask butuh extension tambahan |
| Queue | ARQ | Celery, RQ | ARQ async-native dan lebih ringan dari Celery untuk project ini |
| Transcription | Groq Whisper | OpenAI Whisper API, local Whisper | Groq gratis dan 10x lebih cepat |
| LLM | Gemini 2.0 Flash | GPT-4o, Claude | Gemini gratis tier paling generous untuk development |
| Diarization | pyannote | SpeechBrain, NeMo | pyannote memiliki DER terendah di open-source |
| Linter | ruff | flake8, pylint | ruff 100x lebih cepat, menggabungkan banyak tools |