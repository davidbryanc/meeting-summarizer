from pydantic import BaseModel

class ActionItem(BaseModel):
    task: str
    assignee: str | None = None
    priority: str = "medium"

class MeetingSummary(BaseModel):
    summary: str
    key_decisions: list[str]
    action_items: list[ActionItem]
    topics_discussed: list[str]

class TranscriptChunk(BaseModel):
    text: str
    chunk_index: int
    total_chunks: int

class DiarizationResult(BaseModel):
    segments: list[dict]
    speaker_count: int
    speaker_transcript: str