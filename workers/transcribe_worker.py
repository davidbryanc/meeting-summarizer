import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from arq import cron
from arq.connections import RedisSettings
from config.settings import settings
from services.transcriber import TranscriberService
from services.file_handler import FileHandlerService
from utils.logger import get_logger

logger = get_logger("worker")
transcriber = TranscriberService()
file_handler = FileHandlerService()


async def transcribe_job(
    ctx: dict, job_id: str, audio_path_str: str, original_video_str: str | None
):
    """
    ARQ job function — dijalankan oleh worker di background.
    ctx berisi redis connection yang diinject ARQ otomatis.
    """
    redis = ctx["redis"]
    audio_path = Path(audio_path_str)
    original_video = Path(original_video_str) if original_video_str else None

    logger.info(f"Worker memproses job: {job_id}")

    try:
        # Update status ke processing
        await redis.hset(
            f"job:{job_id}",
            mapping={
                "status": "processing",
                "progress": "10",
                "message": "Transcribing audio...",
            },
        )

        transcript = transcriber.transcribe(audio_path)

        file_handler.cleanup(audio_path, original_video)

        # Update status ke completed
        await redis.hset(
            f"job:{job_id}",
            mapping={
                "status": "completed",
                "progress": "100",
                "message": "Transcription complete",
                "transcript": transcript,
                "char_count": str(len(transcript)),
            },
        )

        # Set TTL 1 jam — hapus otomatis dari Redis
        await redis.expire(f"job:{job_id}", 3600)

        logger.info(f"Job {job_id} selesai: {len(transcript)} karakter")

    except Exception as e:
        logger.error(f"Job {job_id} gagal: {e}")
        file_handler.cleanup(audio_path, original_video)
        await redis.hset(
            f"job:{job_id}",
            mapping={
                "status": "failed",
                "progress": "0",
                "message": "Transcription failed",
                "error": str(e),
            },
        )
        await redis.expire(f"job:{job_id}", 3600)


class WorkerSettings:
    """Konfigurasi ARQ worker."""

    functions = [transcribe_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 600  # 10 menit timeout per job
    keep_result = 3600  # simpan result 1 jam
