import asyncio
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from models.api_schemas import TranscribeResponse, JobStatus
from api.job_store import create_job, update_job
from services.file_handler import FileHandlerService
from services.transcriber import TranscriberService
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("api.transcribe")
file_handler = FileHandlerService()
transcriber = TranscriberService()


async def _run_transcribe(job_id: str, audio_path: Path, original_video: Path | None):
    """Background task — jalankan transcribe dan update job status."""
    try:
        update_job(job_id, status=JobStatus.processing, progress=10, message="Transcribing audio...")
        logger.info(f"Job {job_id}: mulai transcribe {audio_path.name}")

        # Run di thread pool supaya tidak block event loop
        loop = asyncio.get_event_loop()
        transcript = await loop.run_in_executor(
            None, transcriber.transcribe, audio_path
        )

        file_handler.cleanup(audio_path, original_video)

        update_job(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="Transcription complete",
            result={"transcript": transcript, "char_count": len(transcript)},
        )
        logger.info(f"Job {job_id}: selesai — {len(transcript)} karakter")

    except Exception as e:
        logger.error(f"Job {job_id}: gagal — {str(e)}")
        file_handler.cleanup(audio_path, original_video)
        update_job(
            job_id,
            status=JobStatus.failed,
            progress=0,
            message="Transcription failed",
            error=str(e),
        )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    filename = file.filename or "upload"
    data = await file.read()

    # Validasi
    is_valid, error_msg = file_handler.validate(filename, len(data))
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Simpan dan prepare audio
    saved_path = file_handler.save(filename, data)
    audio_path, original_video = file_handler.prepare_audio(saved_path)

    # Buat job dan jalankan di background
    job_id = create_job()
    background_tasks.add_task(_run_transcribe, job_id, audio_path, original_video)

    logger.info(f"Job {job_id} dibuat untuk file: {filename}")

    return TranscribeResponse(
        job_id=job_id,
        status=JobStatus.pending,
        message="Transcription started",
    )