from __future__ import annotations

from functools import cached_property
from pathlib import Path

from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_size: str, compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.compute_type = compute_type

    @cached_property
    def model(self) -> WhisperModel:
        return WhisperModel(self.model_size, compute_type=self.compute_type)

    def transcribe(self, audio_path: Path, language: str | None = None) -> tuple[str, str | None]:
        segments, info = self.model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=True,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        detected = getattr(info, "language", None)
        return text, detected
