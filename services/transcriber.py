from pathlib import Path
from config.settings import settings
from utils.audio_utils import split_audio_into_chunks, cleanup_chunks
from utils.logger import get_logger
logger = get_logger("transcriber")

class TranscriberService:

    def __init__(self, provider: str = None):
        self.provider = provider or settings.transcription_provider

    def transcribe(self, audio_path: Path) -> str:
        logger.info(f"Mulai transcribe: {audio_path.name}")
        chunks = split_audio_into_chunks(audio_path)
        is_chunked = len(chunks) > 1
        if is_chunked:
            logger.info(f"Audio dipotong menjadi {len(chunks)} chunks")

        try:
            transcripts = []
            for i, chunk in enumerate(chunks):
                logger.debug(f"Transcribe chunk {i+1}/{len(chunks)}")
                if self.provider == "groq":
                    text = self._transcribe_groq(chunk)
                elif self.provider == "local":
                    text = self._transcribe_local(chunk)
                else:
                    raise ValueError(f"Provider tidak dikenal: {self.provider}")
                transcripts.append(text)

            result = "\n\n".join(transcripts)
            logger.info(f"Transcribe selesai: {len(result)} karakter")
            return result

        finally:
            if is_chunked:
                cleanup_chunks(chunks)

    def _transcribe_groq(self, audio_path: Path) -> str:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)

        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                response_format="text",
                # language="en",  # nyalakan kalau mau fokus di 1 bahasa
            )
        return result

    def _transcribe_local(self, audio_path: Path) -> str:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path))
        return result["text"]