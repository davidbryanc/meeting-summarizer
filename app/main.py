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
from utils.export import save_transcript, save_summary, save_summary_pdf
from utils.logger import get_logger

logger = get_logger("main")
file_handler = FileHandlerService()
transcriber = TranscriberService()
llm_processor = LLMProcessorService()
diarizer = DiarizerService()


@cl.on_chat_start
async def on_chat_start():
    logger.info("Session baru dimulai")
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
    chat_history = cl.user_session.get("chat_history") or []

    # Toggle diarization
    if not message.elements:
        text = message.content.lower().strip()

        if "aktifkan diarization" in text:
            cl.user_session.set("diarization_enabled", True)
            await cl.Message(content="Identifikasi pembicara **diaktifkan**.").send()
            return

        if "matikan diarization" in text:
            cl.user_session.set("diarization_enabled", False)
            await cl.Message(content="Identifikasi pembicara **dimatikan**. Pipeline akan lebih cepat.").send()
            return

        # Q&A mode — transcript sudah ada
        if transcript:
            await _handle_qa(message.content, transcript, chat_history)
            return

        # Belum ada transcript
        await cl.Message(
            content="Silakan upload file audio atau video meeting kamu untuk memulai."
        ).send()
        return

    # --- PIPELINE: ada file yang diupload ---
    for element in message.elements:
        if not hasattr(element, "path") or not element.path:
            await cl.Message(content="File tidak terbaca, coba upload ulang.").send()
            return

        filename = element.name
        diarization_enabled = cl.user_session.get("diarization_enabled")

        with open(element.path, "rb") as f:
            data = f.read()

        is_valid, error_msg = file_handler.validate(filename, len(data))
        if not is_valid:
            await cl.Message(content=f"File ditolak: {error_msg}").send()
            return

        saved_path = file_handler.save(filename, data)
        audio_path, original_video = file_handler.prepare_audio(saved_path)

        if original_video:
            await cl.Message(content="Audio berhasil di-extract dari video.").send()

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

        file_handler.cleanup(audio_path, original_video)

        final_transcript = speaker_transcript if speaker_transcript else transcript
        cl.user_session.set("transcript", final_transcript)
        cl.user_session.set("original_filename", filename)
        cl.user_session.set("chat_history", [])  # reset history untuk meeting baru

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

        try:
            summary = llm_processor.parse_summary(raw_json)
            cl.user_session.set("summary_object", summary)
        except Exception as e:
            await cl.Message(
                content=f"Gagal memparse summary: {str(e)}\n\nRaw:\n```\n{raw_json[:500]}\n```"
            ).send()
            return

        await _display_summary(summary)

        transcript_path = save_transcript(final_transcript, filename)
        summary_path = save_summary(summary, filename)

        try:
            pdf_path = save_summary_pdf(summary, filename)
            pdf_info = f"\n- Summary PDF: `{pdf_path}`"
        except Exception as e:
            logger.warning(f"PDF export gagal: {e}")
            pdf_info = ""

        await cl.Message(
        content=(
            "Selesai! Kamu sekarang bisa:\n"
            "- Ketik pertanyaan untuk **tanya jawab** tentang isi meeting\n"
            "- Ketik `export transcript` untuk download transcript\n"
            "- Ketik `export summary` untuk download summary PDF"
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
        
async def _handle_qa(question: str, transcript: str, chat_history: list[dict]):
    text = question.lower().strip()

    # Export commands
    if "export transcript" in text:
        filename = cl.user_session.get("original_filename") or "meeting"
        path = save_transcript(transcript, filename)
        await cl.Message(
            content=f"Transcript tersimpan di `{path}`. Kamu bisa buka file ini langsung dari folder `outputs/`."
        ).send()
        return

    if "export summary" in text:
        filename = cl.user_session.get("original_filename") or "meeting"
        summary_obj = cl.user_session.get("summary_object")
        if not summary_obj:
            await cl.Message(content="Summary belum tersedia, coba upload ulang file meeting.").send()
            return
        try:
            pdf_path = save_summary_pdf(summary_obj, filename)
            await cl.Message(
                content=f"Summary PDF tersimpan di `{pdf_path}`."
            ).send()
        except Exception as e:
            logger.error(f"PDF export gagal: {e}")
            await cl.Message(content=f"Export PDF gagal: {str(e)}").send()
        return

    # Q&A biasa — lanjut ke LLM
    chat_history.append({"role": "user", "content": question})
    response_text = ""
    response_msg = cl.Message(content="")
    await response_msg.send()

    try:
        async for token in llm_processor.answer_question_stream(
            transcript=transcript,
            question=question,
            history=chat_history[:-1],
        ):
            response_text += token
            await response_msg.stream_token(token)
        await response_msg.update()
    except Exception as e:
        await cl.Message(content=f"Gagal menjawab: {str(e)}").send()
        return

    chat_history.append({"role": "assistant", "content": response_text})
    cl.user_session.set("chat_history", chat_history[-20:])