import os
from pathlib import Path

SUPPORTED_FORMATS = {".mp3", ".mp4", ".wav", ".m4a", ".webm"}
UPLOADS_DIR = Path("uploads")

MAX_SIZE_MB = {
    ".mp3": 100,
    ".wav": 100,
    ".m4a": 100,
    ".webm": 100,
    ".mp4": 500,
}

def is_supported_format(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_FORMATS

def get_max_size_mb(filename: str) -> int:
    ext = Path(filename).suffix.lower()
    return MAX_SIZE_MB.get(ext, 100)

def get_upload_path(filename: str) -> Path:
    UPLOADS_DIR.mkdir(exist_ok=True)
    return UPLOADS_DIR / filename

def extract_audio_from_video(video_path: Path) -> Path:
    from moviepy import VideoFileClip
    audio_path = video_path.with_suffix(".mp3")
    clip = VideoFileClip(str(video_path))
    clip.audio.write_audiofile(str(audio_path), verbose=False, logger=None)
    clip.close()
    return audio_path

def cleanup_file(file_path: Path) -> None:
    """Hapus file setelah selesai diproses."""
    if file_path.exists():
        file_path.unlink()