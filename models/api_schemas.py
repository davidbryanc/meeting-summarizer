from pydantic import BaseModel
from enum import Enum


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TranscribeResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class TranscribeResult(BaseModel):
    job_id: str
    status: JobStatus
    transcript: str | None = None
    error: str | None = None
    char_count: int = 0


class SummarizeRequest(BaseModel):
    transcript: str
    job_id: str | None = None


class SummarizeResponse(BaseModel):
    job_id: str
    status: JobStatus
    summary: dict | None = None
    error: str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    result: dict | None = None
    error: str | None = None
    progress: int = 0
    message: str = ""
