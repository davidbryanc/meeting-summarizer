import pytest
from unittest.mock import patch
from services.file_handler import FileHandlerService


@pytest.fixture
def handler():
    return FileHandlerService()


def test_validate_valid_mp3(handler):
    """File mp3 valid harus lolos validasi."""
    is_valid, msg = handler.validate("meeting.mp3", 10 * 1024 * 1024)
    assert is_valid is True
    assert msg == ""


def test_validate_invalid_format(handler):
    """File PDF harus ditolak."""
    is_valid, msg = handler.validate("document.pdf", 1024)
    assert is_valid is False
    assert "Format tidak didukung" in msg


def test_validate_file_too_large_mp3(handler):
    """MP3 lebih dari 100MB harus ditolak."""
    is_valid, msg = handler.validate("big.mp3", 200 * 1024 * 1024)
    assert is_valid is False
    assert "terlalu besar" in msg


def test_validate_mp4_size_limit(handler):
    """MP4 punya limit lebih besar — 500MB."""
    # 200MB mp4 harusnya lolos
    is_valid, msg = handler.validate("video.mp4", 200 * 1024 * 1024)
    assert is_valid is True

    # 600MB mp4 harusnya ditolak
    is_valid, msg = handler.validate("video.mp4", 600 * 1024 * 1024)
    assert is_valid is False


def test_save_file(handler, tmp_path):
    """File harus tersimpan di folder uploads."""
    with patch("services.file_handler.get_upload_path") as mock_path:
        output_file = tmp_path / "test.mp3"
        mock_path.return_value = output_file

        result = handler.save("test.mp3", b"fake audio data")

        assert result == output_file
        assert output_file.exists()
        assert output_file.read_bytes() == b"fake audio data"


def test_prepare_audio_non_mp4(handler, tmp_path):
    """File bukan mp4 harus dikembalikan langsung tanpa extract."""
    mp3_file = tmp_path / "test.mp3"
    mp3_file.write_bytes(b"fake mp3")

    audio_path, original_video = handler.prepare_audio(mp3_file)

    assert audio_path == mp3_file
    assert original_video is None


def test_prepare_audio_mp4(handler, tmp_path):
    """File mp4 harus di-extract audionya."""
    mp4_file = tmp_path / "test.mp4"
    mp4_file.write_bytes(b"fake mp4")

    with patch("services.file_handler.extract_audio_from_video") as mock_extract:
        extracted = tmp_path / "test.mp3"
        mock_extract.return_value = extracted

        audio_path, original_video = handler.prepare_audio(mp4_file)

        mock_extract.assert_called_once_with(mp4_file)
        assert original_video == mp4_file
