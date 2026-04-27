import uuid
from models.api_schemas import JobStatus

# Simple in-memory store — akan diupgrade ke Redis di hari 4
_jobs: dict[str, dict] = {}


def create_job() -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": JobStatus.pending,
        "result": None,
        "error": None,
        "progress": 0,
        "message": "Job created",
    }
    return job_id


def update_job(job_id: str, **kwargs) -> None:
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


def delete_job(job_id: str) -> None:
    _jobs.pop(job_id, None)