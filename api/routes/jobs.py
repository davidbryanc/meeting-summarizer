from fastapi import APIRouter, HTTPException
from models.api_schemas import JobStatusResponse
from api.job_store import get_job
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("api.jobs")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
        progress=job.get("progress", 0),
        message=job.get("message", ""),
    )