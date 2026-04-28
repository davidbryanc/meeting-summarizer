from pathlib import Path
from config.settings import settings
from utils.logger import get_logger
logger = get_logger("diarizer")

try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False
    logger.warning("pyannote.audio tidak terinstall — diarization tidak tersedia")


class DiarizerService:

    def __init__(self):
        self._pipeline = None

    def is_available(self) -> bool:
        return PYANNOTE_AVAILABLE

    def _load_pipeline(self):
        if not PYANNOTE_AVAILABLE:
            raise RuntimeError("pyannote.audio tidak terinstall")
        if self._pipeline is not None:
            return self._pipeline
        import torch
        logger.info("Loading pyannote pipeline...")
        self._pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=settings.huggingface_token,
        )
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._pipeline = self._pipeline.to(device)
        logger.info(f"Pipeline loaded, device: {device}")
        return self._pipeline

    def diarize(self, audio_path: Path) -> list[dict]:
        if not PYANNOTE_AVAILABLE:
            raise RuntimeError("pyannote.audio tidak terinstall")
        import torch
        import soundfile as sf
        logger.info(f"Mulai diarization: {audio_path.name}")
        pipeline = self._load_pipeline()
        data, sample_rate = sf.read(str(audio_path), dtype="float32", always_2d=True)
        waveform = torch.from_numpy(data.T)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        audio_input = {"waveform": waveform, "sample_rate": sample_rate}
        diarization = pipeline(audio_input)
        segments = []
        for segment, _, speaker in diarization.speaker_diarization.itertracks(yield_label=True):
            segments.append({
                "speaker": speaker,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
            })
        logger.info(f"Diarization selesai: {len(set(s['speaker'] for s in segments))} pembicara")
        return segments

    def assign_speakers_to_words(
        self,
        word_segments: list[dict],
        diarization_segments: list[dict],
    ) -> list[dict]:
        """
        WhisperX-aware: assign speaker ke setiap word berdasarkan timestamp.
        Jauh lebih akurat dari pendekatan heuristik sebelumnya.
        """
        result = []
        for word in word_segments:
            word_start = word.get("start", 0)
            word_end = word.get("end", word_start)
            word_mid = (word_start + word_end) / 2

            speaker = _find_speaker_at_time(diarization_segments, word_mid)
            result.append({**word, "speaker": speaker})

        return result

    def build_speaker_transcript(self, word_segments_with_speakers: list[dict]) -> str:
        """
        Bangun transcript dengan label speaker dari word segments.
        Gabungkan kata-kata yang speaker-nya sama menjadi satu blok.
        """
        if not word_segments_with_speakers:
            return ""

        lines = []
        current_speaker = None
        current_words = []

        for word in word_segments_with_speakers:
            speaker = word.get("speaker", "UNKNOWN")
            text = word.get("word", "")

            if speaker != current_speaker:
                if current_words:
                    lines.append(f"**{current_speaker}:** {' '.join(current_words)}")
                current_speaker = speaker
                current_words = [text]
            else:
                current_words.append(text)

        if current_words:
            lines.append(f"**{current_speaker}:** {' '.join(current_words)}")

        return "\n\n".join(lines)

    def merge_transcript_with_speakers(
        self,
        transcript: str,
        segments: list[dict],
    ) -> str:
        """Fallback heuristik — dipakai kalau tidak ada word timestamps."""
        if not segments:
            return transcript
        sentences = [s.strip() for s in transcript.split(".") if s.strip()]
        if not sentences:
            return transcript
        total_duration = segments[-1]["end"] if segments else 1
        sentences_per_second = len(sentences) / total_duration
        result_lines = []
        current_speaker = None
        for i, sentence in enumerate(sentences):
            estimated_time = i / sentences_per_second
            speaker = _find_speaker_at_time(segments, estimated_time)
            if speaker != current_speaker:
                current_speaker = speaker
                result_lines.append(f"\n**{speaker}:**")
            result_lines.append(f"{sentence}.")
        return "\n".join(result_lines)


def _find_speaker_at_time(segments: list[dict], time: float) -> str:
    for segment in segments:
        if segment["start"] <= time <= segment["end"]:
            return segment["speaker"]
    if not segments:
        return "UNKNOWN"
    closest = min(segments, key=lambda s: abs(s["start"] - time))
    return closest["speaker"]