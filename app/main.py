import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chainlit as cl
from services.file_handler import FileHandlerService
from services.transcriber import TranscriberService
from services.llm_processor import LLMProcessorService

file_handler = FileHandlerService()
transcriber = TranscriberService()
llm_processor = LLMProcessorService()


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("transcript", None)
    cl.user_session.set("chat_history", [])
    await cl.Message(
        content="Halo! Upload file meeting kamu (mp3, mp4, wav, m4a) untuk memulai."
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    transcript = cl.user_session.get("transcript")

    # Kalau sudah ada transcript, masuk mode Q&A (hari 7)
    # Untuk sekarang arahkan user untuk upload file dulu
    if not message.elements:
        if transcript:
            await cl.Message(
                content="Transcript sudah ada. Mode Q&A akan tersedia di update berikutnya!"
            ).send()
        else:
            await cl.Message(content="Silakan upload file audio atau video dulu ya.").send()
        return

    # --- PIPELINE: upload → transcribe → summarize ---
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
        await cl.Message(content=f"File diterima: `{filename}`").send()

        # 3. Extract audio kalau mp4
        audio_path, original_video = file_handler.prepare_audio(saved_path)
        if original_video:
            await cl.Message(content="Audio berhasil di-extract dari video.").send()

        # 4. Transcribe
        await cl.Message(
            content="Sedang mentranscribe audio... harap tunggu sebentar."
        ).send()

        try:
            transcript = transcriber.transcribe(audio_path)
        except Exception as e:
            await cl.Message(content=f"Transcribe gagal: {str(e)}").send()
            file_handler.cleanup(audio_path, original_video)
            return

        # Cleanup file audio setelah transcribe
        file_handler.cleanup(audio_path, original_video)

        # Simpan transcript di session
        cl.user_session.set("transcript", transcript)

        await cl.Message(
            content=f"Transcribe selesai! ({len(transcript)} karakter). Sedang membuat summary..."
        ).send()

        # 5. Summarize dengan streaming — tampung diam-diam, jangan tampilkan raw JSON
        await cl.Message(content="Sedang membuat summary...").send()

        raw_json = ""
        try:
            async for token in llm_processor.summarize_stream(transcript):
                raw_json += token
        except Exception as e:
            await cl.Message(content=f"Summary gagal: {str(e)}").send()
            return

        # 6. Parse dan tampilkan rapi
        try:
            summary = llm_processor.parse_summary(raw_json)
            await _display_summary(summary)
        except Exception:
            await cl.Message(content=raw_json).send()


async def _display_summary(summary):
    """Tampilkan summary dalam format yang rapi dan mudah dibaca."""

    # Summary utama
    output = f"## Ringkasan Meeting\n\n{summary.summary}\n\n"

    # Topik yang dibahas
    if summary.topics_discussed:
        output += "## Topik yang Dibahas\n"
        for topic in summary.topics_discussed:
            output += f"- {topic}\n"
        output += "\n"

    # Keputusan penting
    if summary.key_decisions:
        output += "## Keputusan Penting\n"
        for decision in summary.key_decisions:
            output += f"- {decision}\n"
        output += "\n"

    # Action items
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