from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

from app.asr.config import ASRConfig, ASRProviderConfig, load_asr_config
from app.config import AppConfig


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str | None
    language_probability: float
    avg_logprob: float
    no_speech_prob: float
    compression_ratio: float


class Transcriber:
    def __init__(self, model_size: str, compute_type: str = 'int8') -> None:
        self.model_size = model_size
        self.compute_type = compute_type

    @cached_property
    def model(self) -> WhisperModel:
        return WhisperModel(self.model_size, compute_type=self.compute_type)

    def transcribe_result(
        self, audio_path: Path, language: str | None = None
    ) -> TranscriptionResult:
        segments, info = self.model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=True,
        )

        segment_list = list(segments)
        text = ' '.join(
            segment.text.strip() for segment in segment_list if segment.text.strip()
        ).strip()

        detected = getattr(info, 'language', None)
        language_probability = float(getattr(info, 'language_probability', 1.0) or 1.0)
        avg_logprob_values = [
            float(segment.avg_logprob)
            for segment in segment_list
            if getattr(segment, 'avg_logprob', None) is not None
        ]
        no_speech_values = [
            float(segment.no_speech_prob)
            for segment in segment_list
            if getattr(segment, 'no_speech_prob', None) is not None
        ]
        compression_values = [
            float(segment.compression_ratio)
            for segment in segment_list
            if getattr(segment, 'compression_ratio', None) is not None
        ]

        avg_logprob = (
            sum(avg_logprob_values) / len(avg_logprob_values)
            if avg_logprob_values
            else 0.0
        )
        no_speech_prob = (
            sum(no_speech_values) / len(no_speech_values) if no_speech_values else 0.0
        )
        compression_ratio = (
            sum(compression_values) / len(compression_values)
            if compression_values
            else 0.0
        )

        return TranscriptionResult(
            text=text,
            language=detected,
            language_probability=language_probability,
            avg_logprob=avg_logprob,
            no_speech_prob=no_speech_prob,
            compression_ratio=compression_ratio,
        )

    def transcribe(
        self, audio_path: Path, language: str | None = None
    ) -> tuple[str, str | None]:
        result = self.transcribe_result(audio_path, language=language)
        return result.text, result.language


class PhoWhisperTranscriber:
    def __init__(
        self,
        model: str,
        device: str = 'auto',
        torch_dtype: str = 'auto',
        chunk_length_s: int = 30,
        batch_size: int = 8,
    ) -> None:
        self.model_name = model
        self.device = device
        self.torch_dtype = torch_dtype
        self.chunk_length_s = chunk_length_s
        self.batch_size = batch_size

    @cached_property
    def pipeline(self) -> Any:
        import torch
        from transformers import pipeline

        model_kwargs: dict[str, Any] = {}
        if self.torch_dtype == 'float16':
            model_kwargs['torch_dtype'] = torch.float16
        elif self.torch_dtype == 'float32':
            model_kwargs['torch_dtype'] = torch.float32
        elif self.torch_dtype == 'bfloat16':
            model_kwargs['torch_dtype'] = torch.bfloat16

        device = self.device
        if device == 'auto':
            if getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available():
                device = 'mps'
            elif torch.cuda.is_available():
                device = 0
            else:
                device = 'cpu'

        return pipeline(
            'automatic-speech-recognition',
            model=self.model_name,
            device=device,
            chunk_length_s=self.chunk_length_s,
            batch_size=self.batch_size,
            model_kwargs=model_kwargs or None,
        )

    def transcribe_result(
        self, audio_path: Path, language: str | None = None
    ) -> TranscriptionResult:
        generate_kwargs: dict[str, Any] = {}
        normalized = _normalize_language(language)
        if normalized == 'vi':
            generate_kwargs['language'] = 'vi'

        result = self.pipeline(
            str(audio_path),
            generate_kwargs=generate_kwargs or None,
            return_timestamps=False,
        )
        text = str(result.get('text', '')).strip()
        detected = normalized or 'vi'
        return TranscriptionResult(
            text=text,
            language=detected,
            language_probability=1.0,
            avg_logprob=0.0,
            no_speech_prob=0.0,
            compression_ratio=0.0,
        )

    def transcribe(
        self, audio_path: Path, language: str | None = None
    ) -> tuple[str, str | None]:
        result = self.transcribe_result(audio_path, language=language)
        return result.text, result.language


class RoutingTranscriber:
    def __init__(self, config: ASRConfig, profile_name: str) -> None:
        self.config = config
        self.profile_name = profile_name
        self.profile = config.profile(profile_name)
        self._instances: dict[str, Any] = {}

    def _provider_for_language(self, language: str | None) -> str:
        normalized = _normalize_language(language)
        if normalized and normalized in self.profile.language_overrides:
            return self.profile.language_overrides[normalized]
        return self.profile.default_provider

    def _get_instance(self, provider_name: str) -> Any:
        if provider_name in self._instances:
            return self._instances[provider_name]

        provider = self.config.providers.get(provider_name)
        if provider is None:
            raise RuntimeError(f"ASR provider '{provider_name}' is not defined")

        instance = _build_provider(provider)
        self._instances[provider_name] = instance
        return instance

    def transcribe_result(
        self, audio_path: Path, language: str | None = None
    ) -> TranscriptionResult:
        if language:
            provider_name = self._provider_for_language(language)
            provider = self._get_instance(provider_name)
            return provider.transcribe_result(audio_path, language=language)

        default_provider_name = self.profile.default_provider
        default_provider = self._get_instance(default_provider_name)
        result = default_provider.transcribe_result(audio_path, language=None)

        detected = _normalize_language(result.language)
        if not detected:
            return result

        reroute_provider_name = self.profile.language_overrides.get(detected)
        if not reroute_provider_name or reroute_provider_name == default_provider_name:
            return result

        reroute_provider = self._get_instance(reroute_provider_name)
        rerouted = reroute_provider.transcribe_result(audio_path, language=detected)
        return rerouted if rerouted.text.strip() else result

    def transcribe(
        self, audio_path: Path, language: str | None = None
    ) -> tuple[str, str | None]:
        result = self.transcribe_result(audio_path, language=language)
        return result.text, result.language


def _normalize_language(language: str | None) -> str | None:
    if not language:
        return None
    normalized = language.strip().lower()
    if not normalized:
        return None
    return normalized.split('-', 1)[0]


def _build_provider(provider: ASRProviderConfig) -> Any:
    provider_type = provider.type
    if provider_type == 'faster_whisper':
        return Transcriber(
            provider.get('model_size', 'small'),
            compute_type=provider.get('compute_type', 'int8'),
        )
    if provider_type == 'phowhisper':
        model = str(provider.get('model', '')).strip()
        if not model:
            raise RuntimeError('PhoWhisper provider requires model')
        return PhoWhisperTranscriber(
            model=model,
            device=str(provider.get('device', 'auto')),
            torch_dtype=str(provider.get('torch_dtype', 'auto')),
            chunk_length_s=int(provider.get('chunk_length_s', 30)),
            batch_size=int(provider.get('batch_size', 8)),
        )
    raise RuntimeError(f'Unsupported ASR provider type: {provider_type}')


def build_transcriber_for_profile(config: AppConfig, profile_name: str) -> RoutingTranscriber:
    asr_config = load_asr_config(config.asr_config_path)
    return RoutingTranscriber(asr_config, profile_name)
