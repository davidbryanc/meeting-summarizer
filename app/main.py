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

logger = get_logger("chainlit")
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

    # --- PIPELINE via FastAPI ---
    for element in message.elements:
        if not hasattr(element, "path") or not element.path:
            await cl.Message(content="File tidak terbaca, coba upload ulang.").send()
            return

        filename = element.name

        with open(element.path, "rb") as f:
            data = f.read()

        # 1. Kirim ke FastAPI /transcribe
        await cl.Message(
            content="**Langkah 1/3** — Mengirim audio ke API untuk transcribe..."
        ).send()

        async with httpx.AsyncClient(timeout=300) as client:
            try:
                resp = await client.post(
                    f"{API_BASE}/transcribe",
                    files={"file": (filename, data, "audio/mpeg")},
                )
                if resp.status_code != 200:
                    await cl.Message(content=f"API error: {resp.text}").send()
                    return

                job = resp.json()
                job_id = job["job_id"]
                logger.info(f"Transcribe job dibuat: {job_id}")

            except Exception as e:
                await cl.Message(content=f"Gagal kirim ke API: {str(e)}").send()
                return

            # 2. Poll sampai selesai
            await cl.Message(
                content="**Langkah 1/3** — Transcribing via Groq Whisper..."
            ).send()

            try:
                result = await poll_job(client, job_id)
            except TimeoutError:
                await cl.Message(content="Transcribe timeout. Coba file yang lebih pendek.").send()
                return

            if result["status"] == "failed":
                await cl.Message(content=f"Transcribe gagal: {result.get('error')}").send()
                return

            transcript = result["result"]["transcript"]
            char_count = result["result"]["char_count"]

            cl.user_session.set("transcript", transcript)
            cl.user_session.set("original_filename", filename)
            cl.user_session.set("chat_history", [])

            await cl.Message(
                content=f"**Langkah 2/3** — Transcript selesai ({char_count} karakter). Membuat summary..."
            ).send()

            # 3. Summarize dengan streaming langsung dari llm_processor
            # Tetap pakai streaming direct — lebih responsif dari polling
            raw_json = ""
            try:
                async for token in llm_processor.summarize_stream(transcript):
                    raw_json += token
            except Exception as e:
                await cl.Message(content=f"Summary gagal: {str(e)}").send()
                return

        # 4. Parse dan tampilkan
        try:
            from services.llm_processor import LLMProcessorService
            summary = llm_processor.parse_summary(raw_json)
            cl.user_session.set("summary_object", summary)
        except Exception as e:
            await cl.Message(
                content=f"Gagal parse summary: {str(e)}\n\nRaw:\n```\n{raw_json[:300]}\n```"
            ).send()
            return

        await _display_summary(summary)

        # 5. Auto-save ke outputs/
        save_transcript(transcript, filename)
        save_summary(summary, filename)

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