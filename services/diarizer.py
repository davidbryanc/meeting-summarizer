from pathlib import Path
from config.settings import settings
from utils.logger import get_logger
logger = get_logger("diarizer")

class DiarizerService:

    def __init__(self):
        self._pipeline = None

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        logger.info("Loading pyannote pipeline (pertama kali — bisa beberapa menit)...")

        from pyannote.audio import Pipeline
        import torch

        self._pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=settings.huggingface_token,
        )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._pipeline = self._pipeline.to(device)

        return self._pipeline

    def diarize(self, audio_path: Path) -> list[dict]:
        logger.info(f"Mulai diarization: {audio_path.name}")
        import torch
        import soundfile as sf

        pipeline = self._load_pipeline()

        data, sample_rate = sf.read(str(audio_path), dtype="float32", always_2d=True)
        waveform = torch.from_numpy(data.T)

        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        audio_input = {
            "waveform": waveform,
            "sample_rate": sample_rate,
        }

        diarization = pipeline(audio_input)

        segments = []

        # API baru pyannote — iterasi langsung dari object diarization
        for segment, _, speaker in diarization.speaker_diarization.itertracks(yield_label=True):
            segments.append({
                "speaker": speaker,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
            })
        return segments

    def merge_transcript_with_speakers(
        self,
        transcript: str,
        segments: list[dict]
    ) -> str:
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
    closest = min(segments, key=lambda s: abs(s["start"] - time))
    return closest["speaker"]