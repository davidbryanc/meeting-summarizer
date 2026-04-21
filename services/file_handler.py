from pathlib import Path
from utils.audio_utils import (
    is_supported_format,
    get_max_size_mb,
    get_upload_path,
    extract_audio_from_video,
    cleanup_file,
)

class FileHandlerService:

    def validate(self, filename: str, file_size_bytes: int) -> tuple[bool, str]:
        if not is_supported_format(filename):
            return False, "Format tidak didukung. Gunakan: mp3, mp4, wav, m4a, webm."

        size_mb = file_size_bytes / (1024 * 1024)
        max_mb = get_max_size_mb(filename)
        if size_mb > max_mb:
            return False, f"File terlalu besar ({size_mb:.1f} MB). Maksimal {max_mb} MB untuk format ini."

        return True, ""

    def save(self, filename: str, data: bytes) -> Path:
        path = get_upload_path(filename)
        path.write_bytes(data)
        return path

    def prepare_audio(self, file_path: Path) -> tuple[Path, Path | None]:
        """
        Return (audio_path, file_to_cleanup).
        Kalau mp4: audio_path = mp3 hasil extract, file_to_cleanup = mp4 asli.
        Kalau bukan mp4: audio_path = file asli, file_to_cleanup = None.
        """
        if file_path.suffix.lower() == ".mp4":
            audio_path = extract_audio_from_video(file_path)
            return audio_path, file_path  # mp4 asli siap dihapus
        return file_path, None

    def cleanup(self, *paths: Path | None) -> None:
        for path in paths:
            if path:
                cleanup_file(path)