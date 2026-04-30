from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from models.api_schemas import SummarizeRequest, SummarizeResponse, JobStatus
from api.job_store import create_job, update_job
from services.llm_processor import LLMProcessorService
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("api.summarize")
llm_processor = LLMProcessorService()


@router.post("/summarize/stream")
async def summarize_stream(request: SummarizeRequest):
    """
    Streaming endpoint — return token per token via Server-Sent Events.
    Chainlit konsumsi ini langsung untuk streaming UI.
    """
    logger.info(f"Summarize stream request: {len(request.transcript)} karakter")

    async def generate():
        try:
            async for token in llm_processor.summarize_stream(request.transcript):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Summarize stream error: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _run_summarize(job_id: str, transcript: str):
    """Background task untuk summarize non-streaming."""
    try:
        update_job(
            job_id, status=JobStatus.processing, progress=10, message="Summarizing..."
        )

        raw_json = ""
        async for token in llm_processor.summarize_stream(transcript):
            raw_json += token

        summary = llm_processor.parse_summary(raw_json)

        update_job(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="Summary complete",
            result=summary.model_dump(),
        )
        logger.info(f"Job {job_id}: summary selesai")

    except Exception as e:
        logger.error(f"Job {job_id}: summarize gagal — {e}")
        update_job(job_id, status=JobStatus.failed, error=str(e))


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest, background_tasks: BackgroundTasks):
    """Non-streaming — return job_id, polling via /jobs/{job_id}."""
    job_id = create_job()
    background_tasks.add_task(_run_summarize, job_id, request.transcript)
    return SummarizeResponse(job_id=job_id, status=JobStatus.pending)
