from fastapi import APIRouter, UploadFile, File, HTTPException
from arq.connections import ArqRedis, create_pool, RedisSettings
from models.api_schemas import TranscribeResponse, JobStatus
from api.job_store import create_job
from services.file_handler import FileHandlerService
from config.settings import settings
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("api.transcribe")
file_handler = FileHandlerService()


async def get_arq_pool() -> ArqRedis:
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    filename = file.filename or "upload"
    data = await file.read()

    # Validasi
    is_valid, error_msg = file_handler.validate(filename, len(data))
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Simpan file
    saved_path = file_handler.save(filename, data)
    audio_path, original_video = file_handler.prepare_audio(saved_path)

    # Buat job di Redis
    job_id = await create_job()

    # Enqueue ke ARQ worker
    arq = await get_arq_pool()
    await arq.enqueue_job(
        "transcribe_job",
        job_id,
        str(audio_path),
        str(original_video) if original_video else None,
        _job_id=job_id,
    )

    logger.info(f"Job {job_id} di-enqueue untuk file: {filename}")

    return TranscribeResponse(
        job_id=job_id,
        status=JobStatus.pending,
        message="Transcription queued",
    )
