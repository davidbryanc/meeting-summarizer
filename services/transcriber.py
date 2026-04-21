from pathlib import Path
from config.settings import settings
from utils.audio_utils import split_audio_into_chunks, cleanup_chunks


class TranscriberService:

    def __init__(self, provider: str = None):
        self.provider = provider or settings.transcription_provider

    def transcribe(self, audio_path: Path) -> str:
        """
        Entry point utama. Auto-chunking kalau file panjang.
        Return full transcript sebagai string.
        """
        chunks = split_audio_into_chunks(audio_path)
        is_chunked = len(chunks) > 1

        try:
            transcripts = []
            for i, chunk in enumerate(chunks):
                if self.provider == "groq":
                    text = self._transcribe_groq(chunk)
                elif self.provider == "local":
                    text = self._transcribe_local(chunk)
                else:
                    raise ValueError(f"Provider tidak dikenal: {self.provider}")
                transcripts.append(text)

            return "\n\n".join(transcripts)

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
                language="id",  # ganti ke "en" kalau meeting bahasa Inggris
            )
        return result

    def _transcribe_local(self, audio_path: Path) -> str:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path))
        return result["text"]