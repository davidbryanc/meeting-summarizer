from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("api.download")

OUTPUTS_DIR = Path("outputs")


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Serve file dari outputs/ folder untuk download."""
    # Security: pastikan tidak ada path traversal
    safe_name = Path(filename).name
    file_path = OUTPUTS_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail=f"File tidak ditemukan: {safe_name}"
        )

    media_type = "application/pdf" if safe_name.endswith(".pdf") else "text/plain"

    logger.info(f"Download: {safe_name}")
    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type=media_type,
    )


@router.get("/outputs")
async def list_outputs():
    """List semua file yang tersedia di outputs/."""
    if not OUTPUTS_DIR.exists():
        return {"files": []}

    files = [
        {
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "download_url": f"/download/{f.name}",
        }
        for f in OUTPUTS_DIR.iterdir()
        if f.is_file()
    ]
    return {"files": sorted(files, key=lambda x: x["name"])}
