import pytest
import json
from unittest.mock import patch
from services.llm_processor import LLMProcessorService
from models.schemas import MeetingSummary


@pytest.fixture
def processor():
    return LLMProcessorService(provider="gemini")


def test_parse_summary_valid_json(processor, sample_summary_dict):
    """JSON valid harus berhasil di-parse jadi MeetingSummary."""
    raw_json = json.dumps(sample_summary_dict)
    result = processor.parse_summary(raw_json)

    assert isinstance(result, MeetingSummary)
    assert result.summary == sample_summary_dict["summary"]
    assert len(result.key_decisions) == 1
    assert len(result.action_items) == 1
    assert result.action_items[0].assignee == "SPEAKER_01"


def test_parse_summary_with_markdown_fences(processor, sample_summary_dict):
    """JSON yang dibungkus backtick harus tetap bisa di-parse."""
    raw_json = f"```json\n{json.dumps(sample_summary_dict)}\n```"
    result = processor.parse_summary(raw_json)

    assert isinstance(result, MeetingSummary)
    assert result.summary == sample_summary_dict["summary"]


def test_parse_summary_with_extra_text(processor, sample_summary_dict):
    """JSON dengan teks ekstra di sekitarnya harus tetap bisa di-parse."""
    raw_json = f"Here is the summary:\n{json.dumps(sample_summary_dict)}\nDone."
    result = processor.parse_summary(raw_json)

    assert isinstance(result, MeetingSummary)


def test_parse_summary_invalid_json(processor):
    """JSON invalid harus raise exception."""
    with pytest.raises(Exception):
        processor.parse_summary("this is not json at all")


async def test_summarize_stream_yields_tokens(processor):
    """summarize_stream harus yield token-token dari LLM."""
    mock_tokens = ["Hello", " world", " test"]

    async def mock_stream(*args, **kwargs):
        for token in mock_tokens:
            yield token

    with patch.object(processor, "_gemini_stream", mock_stream):
        collected = []
        async for token in processor.summarize_stream("test transcript"):
            collected.append(token)

        assert collected == mock_tokens


async def test_answer_question_stream(processor, sample_transcript):
    """Q&A stream harus yield tokens dan pakai transcript sebagai context."""

    async def mock_stream(*args, **kwargs):
        yield "SPEAKER_01 is responsible."

    with patch.object(processor, "_gemini_stream", mock_stream):
        collected = []
        async for token in processor.answer_question_stream(
            transcript=sample_transcript,
            question="Who brought the mud?",
            history=[],
        ):
            collected.append(token)

        assert len(collected) > 0
        assert "SPEAKER_01" in "".join(collected)
