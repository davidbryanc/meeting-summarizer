import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from api.main import app

# TestClient dari httpx — tidak butuh server running untuk test API
client = TestClient(app)


def test_health_endpoint():
    """Health endpoint harus return 200 dan status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_transcribe_invalid_format():
    """Upload file format tidak didukung harus return 400."""
    with patch("api.routes.transcribe.file_handler") as mock_handler:
        mock_handler.validate.return_value = (False, "Format tidak didukung.")

        response = client.post(
            "/transcribe",
            files={"file": ("test.pdf", b"fake content", "application/pdf")},
        )

        assert response.status_code == 400
        assert "Format tidak didukung" in response.json()["detail"]


async def test_get_job_not_found():
    """Job ID yang tidak ada harus return 404."""
    with patch("api.routes.jobs.get_job", return_value=None):
        response = client.get("/jobs/nonexistent-job-id")
        assert response.status_code == 404


async def test_get_job_completed():
    """Job yang completed harus return transcript di result."""
    mock_job = {
        "status": "completed",
        "progress": "100",
        "message": "Transcription complete",
        "transcript": "Hello world transcript.",
        "char_count": "22",
    }

    with patch("api.routes.jobs.get_job", return_value=mock_job):
        response = client.get("/jobs/some-valid-job-id")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"]["transcript"] == "Hello world transcript."
        assert data["result"]["char_count"] == 22


def test_download_file_not_found():
    """Download file yang tidak ada harus return 404."""
    response = client.get("/download/nonexistent_file.pdf")
    assert response.status_code == 404
