import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chainlit as cl
from services.file_handler import FileHandlerService
from services.transcriber import TranscriberService
from services.llm_processor import LLMProcessorService
from services.diarizer import DiarizerService
from utils.export import save_transcript, save_summary
from config.settings import settings

file_handler = FileHandlerService()
transcriber = TranscriberService()
llm_processor = LLMProcessorService()
diarizer = DiarizerService()


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("transcript", None)
    cl.user_session.set("original_filename", None)
    cl.user_session.set("chat_history", [])
    cl.user_session.set("diarization_enabled", settings.diarization_enabled)

    diarization_status = "aktif" if settings.diarization_enabled else "nonaktif"

    await cl.Message(
        content=(
            "Halo! Selamat datang di **Meeting Summarizer**.\n\n"
            "Upload file rekaman meeting kamu untuk mendapatkan:\n"
            "- Transcript lengkap\n"
            "- Identifikasi pembicara (diarization)\n"
            "- Ringkasan otomatis\n"
            "- Key decisions & action items\n\n"
            f"Format: `mp3`, `mp4`, `wav`, `m4a` — "
            f"Identifikasi pembicara: **{diarization_status}**\n\n"
            "Ketik `aktifkan diarization` atau `matikan diarization` untuk toggle."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    transcript = cl.user_session.get("transcript")

    # Toggle diarization via chat
    if not message.elements:
        text = message.content.lower().strip()

        if "aktifkan diarization" in text:
            cl.user_session.set("diarization_enabled", True)
            await cl.Message(content="Identifikasi pembicara **diaktifkan**. Upload file untuk memproses.").send()
            return

        if "matikan diarization" in text:
            cl.user_session.set("diarization_enabled", False)
            await cl.Message(content="Identifikasi pembicara **dimatikan**. Pipeline akan lebih cepat.").send()
            return

        if transcript:
            await cl.Message(
                content="Mode Q&A akan tersedia segera. Untuk memproses meeting baru, upload file baru."
            ).send()
        else:
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
        diarization_enabled = cl.user_session.get("diarization_enabled")

        with open(element.path, "rb") as f:
            data = f.read()

        # 1. Validasi
        is_valid, error_msg = file_handler.validate(filename, len(data))
        if not is_valid:
            await cl.Message(content=f"File ditolak: {error_msg}").send()
            return

        # 2. Simpan dan extract audio
        saved_path = file_handler.save(filename, data)
        audio_path, original_video = file_handler.prepare_audio(saved_path)

        if original_video:
            await cl.Message(content="Audio berhasil di-extract dari video.").send()

        # 3. Transcribe
        await cl.Message(
            content="**Langkah 1/3** — Mentranscribe audio dengan Groq Whisper..."
        ).send()

        try:
            transcript = transcriber.transcribe(audio_path)
        except Exception as e:
            await cl.Message(content=f"Transcribe gagal: {str(e)}").send()
            file_handler.cleanup(audio_path, original_video)
            return

        await cl.Message(
            content=f"**Langkah 2/3** — Transcript selesai ({len(transcript)} karakter)."
        ).send()

        # 4. Diarization (opsional)
        speaker_transcript = None

        if diarization_enabled:
            await cl.Message(
                content=(
                    "**Langkah 2.5/3** — Mengidentifikasi pembicara...\n"
                    "_(proses ini bisa memakan waktu beberapa menit di CPU)_"
                )
            ).send()

            try:
                from utils.audio_utils import convert_to_wav
                wav_path = convert_to_wav(audio_path)

                segments = diarizer.diarize(wav_path)
                speaker_transcript = diarizer.merge_transcript_with_speakers(
                    transcript, segments
                )
                speaker_count = len(set(s["speaker"] for s in segments))

                # Cleanup wav sementara kalau beda dari audio_path asli
                if wav_path != audio_path:
                    from utils.audio_utils import cleanup_file
                    cleanup_file(wav_path)

                await cl.Message(
                    content=f"Ditemukan **{speaker_count} pembicara** dalam rekaman."
                ).send()
            except Exception as e:
                await cl.Message(
                    content=f"Diarization gagal (pipeline tetap lanjut): {str(e)}"
                ).send()
                speaker_transcript = None

        # Cleanup audio setelah semua proses selesai
        file_handler.cleanup(audio_path, original_video)

        # Simpan ke session
        final_transcript = speaker_transcript if speaker_transcript else transcript
        cl.user_session.set("transcript", final_transcript)
        cl.user_session.set("original_filename", filename)

        # 5. Summarize
        await cl.Message(
            content="**Langkah 3/3** — Membuat summary dengan Gemini..."
        ).send()

        raw_json = ""
        try:
            async for token in llm_processor.summarize_stream(final_transcript):
                raw_json += token
        except Exception as e:
            await cl.Message(content=f"Summary gagal: {str(e)}").send()
            return

        # 6. Parse dan tampilkan
        try:
            summary = llm_processor.parse_summary(raw_json)
        except Exception as e:
            await cl.Message(
                content=f"Gagal memparse summary: {str(e)}\n\nRaw:\n```\n{raw_json[:500]}\n```"
            ).send()
            return

        await _display_summary(summary, speaker_transcript)

        # 7. Simpan ke outputs/
        transcript_path = save_transcript(final_transcript, filename)
        summary_path = save_summary(summary, filename)

        await cl.Message(
            content=(
                f"File tersimpan di:\n"
                f"- Transcript: `{transcript_path}`\n"
                f"- Summary: `{summary_path}`\n\n"
                f"Untuk memproses meeting lain, upload file baru."
            )
        ).send()


async def _display_summary(summary, speaker_transcript=None):
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

    # Tampilkan speaker transcript kalau ada
    if speaker_transcript:
        await cl.Message(
            content=f"## Transcript per Pembicara\n\n{speaker_transcript}"
        ).send()