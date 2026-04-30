import pytest
from unittest.mock import patch
from services.transcriber import TranscriberService


@pytest.fixture
def transcriber():
    return TranscriberService(provider="groq")


def test_transcribe_groq_success(transcriber, sample_audio_path):
    """Groq transcribe harus return string transcript."""
    with patch.object(transcriber, "_transcribe_groq") as mock_groq:
        mock_groq.return_value = "Hello this is a test transcript."

        with patch("services.transcriber.split_audio_into_chunks") as mock_split:
            mock_split.return_value = [sample_audio_path]

            result = transcriber.transcribe(sample_audio_path)

            assert isinstance(result, str)
            assert len(result) > 0
            mock_groq.assert_called_once_with(sample_audio_path)


def test_transcribe_invalid_provider(sample_audio_path):
    """Provider tidak dikenal harus raise ValueError."""
    transcriber = TranscriberService(provider="invalid_provider")

    with patch("services.transcriber.split_audio_into_chunks") as mock_split:
        mock_split.return_value = [sample_audio_path]

        with pytest.raises(ValueError, match="Provider tidak dikenal"):
            transcriber.transcribe(sample_audio_path)


def test_transcribe_multiple_chunks(transcriber, tmp_path):
    """Transcript dari multiple chunks harus digabung dengan newline."""
    chunk1 = tmp_path / "chunk_001.mp3"
    chunk2 = tmp_path / "chunk_002.mp3"
    chunk1.write_bytes(b"fake")
    chunk2.write_bytes(b"fake")

    with patch.object(transcriber, "_transcribe_groq") as mock_groq:
        mock_groq.side_effect = ["First chunk text.", "Second chunk text."]

        with patch("services.transcriber.split_audio_into_chunks") as mock_split:
            mock_split.return_value = [chunk1, chunk2]

            with patch("services.transcriber.cleanup_chunks"):
                result = transcriber.transcribe(chunk1)

                assert "First chunk text." in result
                assert "Second chunk text." in result
                assert mock_groq.call_count == 2


def test_transcribe_with_timestamps_fallback(transcriber, sample_audio_path):
    """Provider non-whisperx harus fallback ke plain transcribe."""
    with patch.object(transcriber, "transcribe") as mock_transcribe:
        mock_transcribe.return_value = "plain transcript"

        result = transcriber.transcribe_with_timestamps(sample_audio_path)

        assert result["language"] == "unknown"
        assert result["word_segments"] == []
        assert result["segments"][0]["text"] == "plain transcript"
