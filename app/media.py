from __future__ import annotations

import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass



def extract_audio_to_wav(input_path: Path, output_path: Path) -> Path:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaError(proc.stderr.strip() or "ffmpeg failed")
    return output_path
