from pathlib import Path
from utils.logger import get_logger

logger = get_logger("whisperx_transcriber")


class WhisperXTranscriber:
    """
    Transcriber berbasis WhisperX — menghasilkan word-level timestamps
    yang memungkinkan diarization jauh lebih akurat.
    """

    def __init__(self, model_size: str = "base", language: str = None):
        self.model_size = model_size
        self.language = language
        self._model = None
        self._align_model = None
        self._align_metadata = None

    def _load_model(self):
        if self._model is not None:
            return
        import whisperx
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float32"  # CPU safe

        logger.info(f"Loading WhisperX model '{self.model_size}' on {device}...")
        self._model = whisperx.load_model(
            self.model_size,
            device=device,
            compute_type=compute_type,
            language=self.language,
        )
        logger.info("WhisperX model loaded")
        
    
    def _load_align_model(self, language_code: str):
        import whisperx
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        LANGUAGE_MODEL_MAP = {
            "id": "indonesian-nlp/wav2vec2-large-xlsr-indonesian",
            "ja": "jonatasgrosman/wav2vec2-large-xlsr-53-japanese",
            "zh": "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
        }

        if self._align_model is None or getattr(self, "_align_lang", None) != language_code:
            custom_model = LANGUAGE_MODEL_MAP.get(language_code)
            logger.info(f"Loading alignment model untuk bahasa: {language_code}")
            try:
                self._align_model, self._align_metadata = whisperx.load_align_model(
                    language_code=language_code,
                    device=device,
                    model_name=custom_model,  # None = pakai default kalau tersedia
                )
                self._align_lang = language_code
                logger.info(f"Alignment model loaded: {custom_model or 'default'}")
            except Exception as e:
                logger.warning(f"Alignment model tidak tersedia untuk '{language_code}': {e}")
                self._align_model = None
                self._align_metadata = None

    def transcribe_with_timestamps(self, audio_path: Path) -> dict:
        """
        Transcribe dan return hasil dengan word-level timestamps.
        Return format:
        {
            "segments": [{"start": 0.0, "end": 1.5, "text": "...", "words": [...]}],
            "language": "en",
            "word_segments": [{"word": "hello", "start": 0.0, "end": 0.3, "score": 0.99}]
        }
        """
        import whisperx

        self._load_model()

        logger.info(f"WhisperX transcribe: {audio_path.name}")

        # Load audio
        audio = whisperx.load_audio(str(audio_path))

        # Transcribe
        result = self._model.transcribe(audio, batch_size=8)
        language = result.get("language", "en")
        logger.info(f"Bahasa terdeteksi: {language}")

        # Align untuk word-level timestamps
        self._load_align_model(language)

        if self._align_model is not None:
            result = whisperx.align(
                result["segments"],
                self._align_model,
                self._align_metadata,
                audio,
                device="cpu",
                return_char_alignments=False,
            )
            logger.info("Word alignment selesai")
        else:
            logger.warning("Skip alignment — model tidak tersedia untuk bahasa ini")

        return {
            "segments": result.get("segments", []),
            "language": language,
            "word_segments": result.get("word_segments", []),
        }

    def transcribe(self, audio_path: Path) -> str:
        """Simple transcribe — return plain text tanpa timestamps."""
        result = self.transcribe_with_timestamps(audio_path)
        return " ".join(
            seg.get("text", "").strip()
            for seg in result["segments"]
        )