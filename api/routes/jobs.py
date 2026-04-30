from fastapi import APIRouter, HTTPException
from models.api_schemas import JobStatusResponse, JobStatus
from api.job_store import get_job
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("api.jobs")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    result = None
    if job.get("status") == "completed":
        result = {
            "transcript": job.get("transcript", ""),
            "char_count": int(job.get("char_count", 0)),
        }

    return JobStatusResponse(
        job_id=job_id,
        status=JobStatus(job.get("status", "pending")),
        result=result,
        error=job.get("error"),
        progress=int(job.get("progress", 0)),
        message=job.get("message", ""),
    )
