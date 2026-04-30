import os
from pyannote.audio import Pipeline

token = os.environ.get("HUGGINGFACE_TOKEN", "")
if token:
    print("Downloading pyannote model...")
    Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=token,
    )
    print("Pyannote model pre-downloaded successfully")
else:
    print("HUGGINGFACE_TOKEN not set, skipping pre-download")
