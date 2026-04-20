from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from faster_whisper import WhisperModel


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str | None
    language_probability: float
    avg_logprob: float
    no_speech_prob: float
    compression_ratio: float


class Transcriber:
    def __init__(self, model_size: str, compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.compute_type = compute_type

    @cached_property
    def model(self) -> WhisperModel:
        return WhisperModel(self.model_size, compute_type=self.compute_type)

    def transcribe_result(self, audio_path: Path, language: str | None = None) -> TranscriptionResult:
        segments, info = self.model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=True,
        )
        segment_list = list(segments)
        text = " ".join(segment.text.strip() for segment in segment_list if segment.text.strip()).strip()
        detected = getattr(info, "language", None)
        language_probability = float(getattr(info, "language_probability", 1.0) or 1.0)

        avg_logprob_values = [
            float(segment.avg_logprob)
            for segment in segment_list
            if getattr(segment, "avg_logprob", None) is not None
        ]
        no_speech_values = [
            float(segment.no_speech_prob)
            for segment in segment_list
            if getattr(segment, "no_speech_prob", None) is not None
        ]
        compression_values = [
            float(segment.compression_ratio)
            for segment in segment_list
            if getattr(segment, "compression_ratio", None) is not None
        ]

        avg_logprob = sum(avg_logprob_values) / len(avg_logprob_values) if avg_logprob_values else 0.0
        no_speech_prob = sum(no_speech_values) / len(no_speech_values) if no_speech_values else 0.0
        compression_ratio = sum(compression_values) / len(compression_values) if compression_values else 0.0

        return TranscriptionResult(
            text=text,
            language=detected,
            language_probability=language_probability,
            avg_logprob=avg_logprob,
            no_speech_prob=no_speech_prob,
            compression_ratio=compression_ratio,
        )

    def transcribe(self, audio_path: Path, language: str | None = None) -> tuple[str, str | None]:
        result = self.transcribe_result(audio_path, language=language)
        return result.text, result.language
