import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chainlit as cl
from services.file_handler import FileHandlerService
from services.transcriber import TranscriberService
from services.llm_processor import LLMProcessorService
from utils.export import save_transcript, save_summary

file_handler = FileHandlerService()
transcriber = TranscriberService()
llm_processor = LLMProcessorService()


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("transcript", None)
    cl.user_session.set("original_filename", None)
    cl.user_session.set("chat_history", [])
    await cl.Message(
        content=(
            "Halo! Selamat datang di **Meeting Summarizer**.\n\n"
            "Upload file rekaman meeting kamu untuk mendapatkan:\n"
            "- Transcript lengkap\n"
            "- Ringkasan otomatis\n"
            "- Key decisions & action items\n\n"
            "Format yang didukung: `mp3`, `mp4`, `wav`, `m4a`, `webm` (maks. 100MB untuk audio, 500MB untuk video)"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    transcript = cl.user_session.get("transcript")

    # Mode Q&A — transcript sudah ada tapi tidak ada file baru
    if not message.elements and transcript:
        await cl.Message(
            content="Mode Q&A akan tersedia segera. Untuk memproses meeting baru, upload file baru."
        ).send()
        return

    if not message.elements:
        await cl.Message(
            content="Silakan upload file audio atau video meeting kamu untuk memulai."
        ).send()
        return

    # --- PIPELINE ---
    for element in message.elements:
        if not hasattr(element, "path") or not element.path:
            await cl.Message(content="File tidak terbaca, coba upload ulang.").send()
            return

        filename = element.name

        with open(element.path, "rb") as f:
            data = f.read()

        # 1. Validasi
        is_valid, error_msg = file_handler.validate(filename, len(data))
        if not is_valid:
            await cl.Message(content=f"File ditolak: {error_msg}").send()
            return

        # 2. Simpan
        saved_path = file_handler.save(filename, data)

        # 3. Extract audio kalau mp4
        audio_path, original_video = file_handler.prepare_audio(saved_path)

        step_msg = await cl.Message(content="").send()

        steps = [
            "Memvalidasi file...",
            "Mempersiapkan audio...",
            "Mentranscribe audio (Groq Whisper)...",
            "Membuat summary (Gemini)...",
        ]

        # Update step 1-2
        await step_msg.update()

        # 4. Transcribe
        await cl.Message(
            content=f"**Langkah 1/3** — Mentranscribe audio dengan Groq Whisper..."
        ).send()

        try:
            transcript = transcriber.transcribe(audio_path)
        except Exception as e:
            await cl.Message(content=f"Transcribe gagal: {str(e)}").send()
            file_handler.cleanup(audio_path, original_video)
            return

        file_handler.cleanup(audio_path, original_video)
        cl.user_session.set("transcript", transcript)
        cl.user_session.set("original_filename", filename)

        await cl.Message(
            content=f"**Langkah 2/3** — Transcript selesai ({len(transcript)} karakter). Menyimpan..."
        ).send()

        # Simpan transcript ke outputs/
        transcript_path = save_transcript(transcript, filename)

        # 5. Summarize
        await cl.Message(
            content="**Langkah 3/3** — Membuat summary dengan Gemini..."
        ).send()

        raw_json = ""
        try:
            async for token in llm_processor.summarize_stream(transcript):
                raw_json += token
        except Exception as e:
            await cl.Message(content=f"Summary gagal: {str(e)}").send()
            return

        # 6. Parse dan tampilkan
        try:
            summary = llm_processor.parse_summary(raw_json)
        except Exception as e:
            await cl.Message(
                content=f"Gagal memparse summary: {str(e)}\n\nRaw output:\n```\n{raw_json[:500]}\n```"
            ).send()
            return

        await _display_summary(summary)

        # Simpan summary ke outputs/
        summary_path = save_summary(summary, filename)

        # 7. Tampilkan link path dan isi singkat
        await cl.Message(
            content=(
                f"Selesai! File tersimpan di:\n\n"
                f"- Transcript: `{transcript_path}`\n"
                f"- Summary: `{summary_path}`\n\n"
                f"Untuk memproses meeting lain, upload file baru."
            )
        ).send()

async def _display_summary(summary):
    output = f"## Ringkasan Meeting\n\n{summary.summary}\n\n"

    if summary.topics_discussed:
        output += "## Topik yang Dibahas\n"
        for topic in summary.topics_discussed:
            output += f"- {topic}\n"
        output += "\n"

    if summary.key_decisions:
        output += "## Keputusan Penting\n"
        for decision in summary.key_decisions:
            output += f"- {decision}\n"
        output += "\n"

    if summary.action_items:
        output += "## Action Items\n"
        for item in summary.action_items:
            assignee = f" — {item.assignee}" if item.assignee else ""
            priority_label = {
                "high": "🔴 High",
                "medium": "🟡 Medium",
                "low": "🟢 Low"
            }.get(item.priority, item.priority)
            output += f"- [{priority_label}]{assignee}: {item.task}\n"
    else:
        output += "## Action Items\nTidak ada action items yang terdeteksi.\n"

    await cl.Message(content=output).send()