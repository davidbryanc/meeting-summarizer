import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import httpx
import chainlit as cl
from utils.logger import get_logger
from utils.export import save_transcript, save_summary, save_summary_pdf
from services.llm_processor import LLMProcessorService
from config.settings import settings

from services.diarizer import DiarizerService
from services.transcriber import TranscriberService
from services.file_handler import FileHandlerService
from utils.audio_utils import convert_to_wav, cleanup_file
from urllib.parse import quote

logger = get_logger("chainlit")

file_handler = FileHandlerService()
diarizer = DiarizerService()
transcriber_service = TranscriberService()
llm_processor = LLMProcessorService()

API_BASE = "http://localhost:8001"


async def poll_job(client: httpx.AsyncClient, job_id: str, timeout: int = 300) -> dict:
    """Poll job status sampai selesai atau timeout."""
    elapsed = 0
    while elapsed < timeout:
        resp = await client.get(f"{API_BASE}/jobs/{job_id}")
        job = resp.json()
        if job["status"] in ("completed", "failed"):
            return job
        await asyncio.sleep(2)
        elapsed += 2
    raise TimeoutError(f"Job {job_id} timeout setelah {timeout} detik")


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("transcript", None)
    cl.user_session.set("original_filename", None)
    cl.user_session.set("chat_history", [])
    cl.user_session.set("diarization_enabled", True)
    cl.user_session.set("summary_object", None)
    logger.info("Session baru dimulai")

    await cl.Message(
        content=(
            "Halo! Selamat datang di **Meeting Summarizer**.\n\n"
            "Upload file rekaman meeting kamu untuk mendapatkan:\n"
            "- Transcript lengkap\n"
            "- Ringkasan otomatis\n"
            "- Key decisions & action items\n\n"
            "Format: `mp3`, `mp4`, `wav`, `m4a` — "
            "Ketik `export transcript` atau `export summary` setelah proses selesai."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    transcript = cl.user_session.get("transcript")
    chat_history = cl.user_session.get("chat_history") or []

    if not message.elements:
        text = message.content.lower().strip()

        if "aktifkan diarization" in text:
            cl.user_session.set("diarization_enabled", True)
            await cl.Message(content="Identifikasi pembicara **diaktifkan**.").send()
            return

        if "matikan diarization" in text:
            cl.user_session.set("diarization_enabled", False)
            await cl.Message(content="Identifikasi pembicara **dimatikan**.").send()
            return

        if transcript:
            await _handle_qa(message.content, transcript, chat_history)
            return

        await cl.Message(
            content="Silakan upload file audio atau video meeting kamu."
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

        file_size = len(data)

        # Import ETA helper
        from utils.eta import estimate_transcribe_seconds, estimate_diarization_seconds, format_eta
        transcribe_eta = format_eta(estimate_transcribe_seconds(file_size))
        diarize_eta = format_eta(estimate_diarization_seconds(file_size))

        # --- Step 1: Transcribe ---
        async with cl.Step(name="Transcribe Audio", type="tool") as step1:
            step1.input = f"File: `{filename}` ({round(file_size/1024/1024, 1)} MB) — ETA: {transcribe_eta}"

            async with httpx.AsyncClient(timeout=300) as client:
                try:
                    resp = await client.post(
                        f"{API_BASE}/transcribe",
                        files={"file": (filename, data, "audio/mpeg")},
                    )
                    if resp.status_code != 200:
                        step1.output = f"Gagal: {resp.text}"
                        await cl.Message(content=f"API error: {resp.text}").send()
                        return

                    job_id = resp.json()["job_id"]
                    logger.info(f"Transcribe job: {job_id}")

                except Exception as e:
                    step1.output = f"Gagal kirim ke API: {str(e)}"
                    await cl.Message(content=f"Error: {str(e)}").send()
                    return

                try:
                    result = await poll_job(client, job_id)
                except TimeoutError:
                    step1.output = "Timeout — coba file yang lebih pendek"
                    await cl.Message(content="Transcribe timeout.").send()
                    return

                if result["status"] == "failed":
                    step1.output = f"Gagal: {result.get('error')}"
                    await cl.Message(content=f"Transcribe gagal: {result.get('error')}").send()
                    return

                transcript = result["result"]["transcript"]
                char_count = result["result"]["char_count"]
                step1.output = f"Selesai — {char_count} karakter"

        cl.user_session.set("transcript", transcript)
        cl.user_session.set("original_filename", filename)
        cl.user_session.set("chat_history", [])

        # --- Step 2: Diarization (opsional) ---
        speaker_transcript = None

        if diarization_enabled and diarizer.is_available():
            async with cl.Step(name="Speaker Diarization", type="tool") as step2:
                step2.input = f"ETA: {diarize_eta} — WhisperX + pyannote"
                try:
                    saved_path_temp = file_handler.save(filename, data)
                    audio_path_temp, original_video_temp = file_handler.prepare_audio(saved_path_temp)
                    wav_path = convert_to_wav(audio_path_temp)

                    wx_result = transcriber_service.transcribe_with_timestamps(audio_path_temp)
                    word_segments = wx_result.get("word_segments", [])
                    diar_segments = diarizer.diarize(wav_path)

                    if wav_path != audio_path_temp:
                        cleanup_file(wav_path)
                    file_handler.cleanup(audio_path_temp, original_video_temp)

                    speaker_count = len(set(s["speaker"] for s in diar_segments))

                    if word_segments:
                        words_with_speakers = diarizer.assign_speakers_to_words(
                            word_segments, diar_segments
                        )
                        speaker_transcript = diarizer.build_speaker_transcript(words_with_speakers)
                        step2.output = f"Ditemukan {speaker_count} pembicara — word-level alignment"
                    else:
                        speaker_transcript = diarizer.merge_transcript_with_speakers(
                            transcript, diar_segments
                        )
                        step2.output = f"Ditemukan {speaker_count} pembicara — heuristik"

                    if speaker_transcript:
                        cl.user_session.set("transcript", speaker_transcript)
                        transcript = speaker_transcript

                except Exception as e:
                    step2.output = f"Gagal: {str(e)}"
                    logger.warning(f"Diarization gagal: {e}")

        # --- Step 3: Summarize ---
        async with cl.Step(name="Generate Summary", type="tool") as step3:
            step3.input = f"Transcript: {len(transcript)} karakter → Gemini 2.5 Flash"
            raw_json = ""
            try:
                async for token in llm_processor.summarize_stream(transcript):
                    raw_json += token
                step3.output = "Summary selesai"
            except Exception as e:
                step3.output = f"Gagal: {str(e)}"
                await cl.Message(content=f"Summary gagal: {str(e)}").send()
                return

        # Parse summary
        try:
            summary = llm_processor.parse_summary(raw_json)
            cl.user_session.set("summary_object", summary)
        except Exception as e:
            await cl.Message(
                content=f"Gagal parse summary: {str(e)}\n\nRaw:\n```\n{raw_json[:300]}\n```"
            ).send()
            return

        await _display_summary(summary)

        # --- Save dan tampilkan download links ---
        transcript_path = save_transcript(transcript, filename)
        summary_path = save_summary(summary, filename)

        transcript_filename = quote(transcript_path.name)
        summary_filename = quote(summary_path.name)

        try:
            pdf_path = save_summary_pdf(summary, filename)
            pdf_filename = quote(pdf_path.name)
            pdf_info = f"- Summary PDF: [download]({API_BASE}/download/{pdf_filename})\n"
        except Exception as e:
            logger.warning(f"PDF export gagal: {e}")
            pdf_info = ""

        await cl.Message(
            content=(
                "**File siap didownload:**\n"
                f"- Transcript: [download]({API_BASE}/download/{transcript_filename})\n"
                f"- Summary MD: [download]({API_BASE}/download/{summary_filename})\n"
                f"{pdf_info}\n"
                "Atau ketik pertanyaan untuk **tanya jawab** tentang isi meeting."
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

    if "export transcript" in text:
        filename = cl.user_session.get("original_filename") or "meeting"
        path = save_transcript(transcript, filename)
        await cl.Message(content=f"Transcript tersimpan di `{path}`.").send()
        return

    if "export summary" in text:
        filename = cl.user_session.get("original_filename") or "meeting"
        summary_obj = cl.user_session.get("summary_object")
        if not summary_obj:
            await cl.Message(content="Summary belum tersedia.").send()
            return
        try:
            pdf_path = save_summary_pdf(summary_obj, filename)
            await cl.Message(content=f"Summary PDF tersimpan di `{pdf_path}`.").send()
        except Exception as e:
            await cl.Message(content=f"Export PDF gagal: {str(e)}").send()
        return

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