import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chainlit as cl
from services.file_handler import FileHandlerService

file_handler = FileHandlerService()

@cl.on_chat_start
async def on_chat_start():
    await cl.Message(
        content="Halo! Upload file meeting kamu (mp3, mp4, wav, m4a) untuk memulai."
    ).send()

@cl.on_message
async def on_message(message: cl.Message):
    # Cek apakah ada file yang diupload
    if not message.elements:
        await cl.Message(content="Silakan upload file audio atau video dulu ya.").send()
        return

    for element in message.elements:
        if not hasattr(element, "path") or not element.path:
            await cl.Message(content="File tidak terbaca, coba upload ulang.").send()
            return

        filename = element.name
        file_path_str = element.path

        # Baca file dari path sementara Chainlit
        with open(file_path_str, "rb") as f:
            data = f.read()

        file_size = len(data)

        # Validasi
        is_valid, error_msg = file_handler.validate(filename, file_size)
        if not is_valid:
            await cl.Message(content=f"File ditolak: {error_msg}").send()
            return

        # Simpan ke uploads/
        saved_path = file_handler.save(filename, data)
        await cl.Message(content=f"File tersimpan: `{saved_path}`").send()

        # Extract audio jika mp4
        await cl.Message(content="Memproses file...").send()
        audio_path, original_video = file_handler.prepare_audio(saved_path)

        if original_video:
            await cl.Message(content=f"Audio berhasil di-extract dari video.").send()

        # Nanti setelah transcribe selesai (hari 3), cleanup dipanggil di sini:
        # file_handler.cleanup(audio_path, original_video)

        await cl.Message(
            content="Siap! Transcription coming soon di hari 3."
        ).send()