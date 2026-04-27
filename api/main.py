import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import transcribe, summarize, jobs
from utils.logger import get_logger

logger = get_logger("api")

app = FastAPI(
    title="Meeting Summarizer API",
    description="REST API for audio transcription and meeting summarization",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transcribe.router, tags=["Transcription"])
app.include_router(summarize.router, tags=["Summarization"])
app.include_router(jobs.router, tags=["Jobs"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "meeting-summarizer-api"}