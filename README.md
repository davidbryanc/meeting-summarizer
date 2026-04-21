# Meeting Summarizer AI

Upload rekaman meeting (mp3/mp4), dapatkan:
- Transcript lengkap
- Summary otomatis
- Key decisions & action items
- Tanya jawab tentang isi meeting

## Tech Stack
- **UI**: Chainlit
- **Speech-to-text**: Whisper via Groq API
- **LLM**: Gemini / OpenAI
- **Deploy**: Railway

## Cara run lokal
```bash
git clone <repo-url>
cd meeting-summarizer
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # isi API key kamu
chainlit run app/main.py
\```

## Status
🚧 Work in progress — Day 2/10
```

---

Setelah semua ini jalan, coba jalankan `chainlit run app/main.py` dan screenshot hasilnya ke sini. Kalau ada error kita debug bareng sebelum lanjut ke hari 2.