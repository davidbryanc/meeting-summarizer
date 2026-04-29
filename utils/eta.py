def estimate_transcribe_seconds(file_size_bytes: int) -> int:
    """Estimasi waktu transcribe berdasarkan ukuran file."""
    size_mb = file_size_bytes / (1024 * 1024)
    # Groq: ~1 detik per MB, minimal 3 detik
    return max(3, int(size_mb * 1.2))

def estimate_diarization_seconds(file_size_bytes: int) -> int:
    """Estimasi waktu diarization di CPU."""
    size_mb = file_size_bytes / (1024 * 1024)
    # pyannote di CPU: ~10 detik per MB
    return max(10, int(size_mb * 10))

def format_eta(seconds: int) -> str:
    if seconds < 60:
        return f"~{seconds} detik"
    minutes = seconds // 60
    return f"~{minutes} menit"