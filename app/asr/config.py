from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ASRProviderConfig:
    type: str
    settings: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)


@dataclass(frozen=True)
class ASRProfileConfig:
    default_provider: str
    language_overrides: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ASRConfig:
    providers: dict[str, ASRProviderConfig]
    profiles: dict[str, ASRProfileConfig]

    def profile(self, name: str) -> ASRProfileConfig:
        profile = self.profiles.get(name)
        if profile is None:
            raise RuntimeError(f"ASR profile '{name}' is not defined")
        return profile


def _normalize_provider(raw: dict[str, Any]) -> ASRProviderConfig:
    raw = dict(raw)
    provider_type = str(raw.pop('type')).strip()
    if not provider_type:
        raise RuntimeError('ASR provider type is required')
    return ASRProviderConfig(type=provider_type, settings=raw)


def _normalize_profile(raw: dict[str, Any]) -> ASRProfileConfig:
    default_provider = str(raw.get('default_provider', '')).strip()
    if not default_provider:
        raise RuntimeError('ASR profile default_provider is required')
    overrides = {
        str(language).strip().lower(): str(provider).strip()
        for language, provider in (raw.get('language_overrides') or {}).items()
        if str(language).strip() and str(provider).strip()
    }
    return ASRProfileConfig(
        default_provider=default_provider,
        language_overrides=overrides,
    )


def load_asr_config(path: Path) -> ASRConfig:
    data = json.loads(path.read_text(encoding='utf-8'))
    providers = {
        str(name): _normalize_provider(value)
        for name, value in (data.get('providers') or {}).items()
    }
    profiles = {
        str(name): _normalize_profile(value)
        for name, value in (data.get('profiles') or {}).items()
    }
    if not providers:
        raise RuntimeError(f'No ASR providers configured in {path}')
    if not profiles:
        raise RuntimeError(f'No ASR profiles configured in {path}')
    return ASRConfig(providers=providers, profiles=profiles)
