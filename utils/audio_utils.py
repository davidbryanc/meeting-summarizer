from pathlib import Path
from pydub import AudioSegment

SUPPORTED_FORMATS = {".mp3", ".mp4", ".wav", ".m4a", ".webm"}
UPLOADS_DIR = Path("uploads")
CHUNK_DURATION_MS = 10 * 60 * 1000  # 10 menit per chunk

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


def split_audio_into_chunks(audio_path: Path) -> list[Path]:
    """
    Potong audio jadi beberapa chunk kalau durasinya panjang.
    Kalau pendek (< 10 menit), return list berisi 1 path saja.
    """
    audio = AudioSegment.from_file(str(audio_path))
    duration_ms = len(audio)

    if duration_ms <= CHUNK_DURATION_MS:
        return [audio_path]

    chunks = []
    chunk_dir = audio_path.parent / f"{audio_path.stem}_chunks"
    chunk_dir.mkdir(exist_ok=True)

    start = 0
    index = 0
    while start < duration_ms:
        end = min(start + CHUNK_DURATION_MS, duration_ms)
        chunk = audio[start:end]
        chunk_path = chunk_dir / f"chunk_{index:03d}.mp3"
        chunk.export(str(chunk_path), format="mp3")
        chunks.append(chunk_path)
        start = end
        index += 1

    return chunks


def cleanup_file(file_path: Path) -> None:
    if file_path.exists():
        file_path.unlink()


def cleanup_chunks(chunk_paths: list[Path]) -> None:
    """Hapus chunk-chunk sementara setelah transcribe selesai."""
    for path in chunk_paths:
        cleanup_file(path)
    if chunk_paths:
        chunk_dir = chunk_paths[0].parent
        if chunk_dir.exists() and not any(chunk_dir.iterdir()):
            chunk_dir.rmdir()


def convert_to_wav(audio_path: Path) -> Path:
    """Convert audio ke wav untuk kompatibilitas soundfile."""
    if audio_path.suffix.lower() == ".wav":
        return audio_path
    wav_path = audio_path.with_suffix(".wav")
    audio = AudioSegment.from_file(str(audio_path))
    audio.export(str(wav_path), format="wav")
    return wav_path
