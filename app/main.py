import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chainlit as cl
from services.file_handler import FileHandlerService
from services.transcriber import TranscriberService

file_handler = FileHandlerService()
transcriber = TranscriberService()

@cl.on_chat_start
async def on_chat_start():
    await cl.Message(
        content="Halo! Upload file meeting kamu (mp3, mp4, wav, m4a) untuk memulai."
    ).send()

@cl.on_message
async def on_message(message: cl.Message):
    if not message.elements:
        await cl.Message(content="Silakan upload file audio atau video dulu ya.").send()
        return

    for element in message.elements:
        if not hasattr(element, "path") or not element.path:
            await cl.Message(content="File tidak terbaca, coba upload ulang.").send()
            return

        filename = element.name

        with open(element.path, "rb") as f:
            data = f.read()

        # Validasi
        is_valid, error_msg = file_handler.validate(filename, len(data))
        if not is_valid:
            await cl.Message(content=f"File ditolak: {error_msg}").send()
            return

        # Simpan
        saved_path = file_handler.save(filename, data)
        await cl.Message(content=f"File diterima: `{filename}`").send()

        # Extract audio kalau mp4
        audio_path, original_video = file_handler.prepare_audio(saved_path)
        if original_video:
            await cl.Message(content="Audio berhasil di-extract dari video.").send()

        # Transcribe
        await cl.Message(content="Sedang mentranscribe audio... ini mungkin butuh beberapa detik.").send()

        try:
            transcript = transcriber.transcribe(audio_path)
        except Exception as e:
            await cl.Message(content=f"Transcribe gagal: {str(e)}").send()
            file_handler.cleanup(audio_path, original_video)
            return

        # Cleanup file upload setelah transcribe selesai
        file_handler.cleanup(audio_path, original_video)

        # Simpan transcript di session untuk dipakai hari 4 (LLM processing)
        cl.user_session.set("transcript", transcript)

        # Tampilkan hasil
        preview = transcript[:500] + "..." if len(transcript) > 500 else transcript

        await cl.Message(
            content=f"Transcribe selesai! Berikut preview-nya:\n\n```\n{preview}\n```"
        ).send()

        await cl.Message(
            content=f"Total karakter: {len(transcript)}. Summary dan action items coming soon di hari 4!"
        ).send()