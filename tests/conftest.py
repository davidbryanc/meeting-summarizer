import pytest
import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_audio_path(tmp_path) -> Path:
    """
    Buat file audio dummy untuk test.
    tmp_path adalah fixture pytest yang otomatis buat folder sementara
    dan hapus setelah test selesai.
    """
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_bytes(b"fake audio content" * 100)
    return audio_file


@pytest.fixture
def sample_transcript() -> str:
    return (
        "Did you wipe your feet? Yes of course I wiped my feet. "
        "Then why is there mud on the carpet? I don't know. "
        "It's not my mud. Well someone brought it into the house."
    )


@pytest.fixture
def sample_summary_dict() -> dict:
    return {
        "summary": "Two speakers discussed mud on the carpet.",
        "key_decisions": ["Wait for mud to dry before vacuuming"],
        "action_items": [
            {"task": "Clean the carpet", "assignee": "SPEAKER_01", "priority": "medium"}
        ],
        "topics_discussed": ["Carpet cleanliness", "Mud removal"],
    }
