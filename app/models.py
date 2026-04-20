from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class FileMode(str, Enum):
    STANDARD = "standard"
    TRANSLATION_ONLY = "translation_only"
    ORIGINAL_ONLY = "original_only"
    SUMMARY = "summary"
    BILINGUAL = "bilingual"


class LiveMode(str, Enum):
    PAIRED = "paired"
    FIXED = "fixed"


@dataclass
class UserSettings:
    ui_language: str = "ru"
    target_language: str = "ru"
    target_language_source: str = "telegram_locale"
    file_mode: str = FileMode.STANDARD.value
    flow_section: str = "home"


@dataclass
class LastJob:
    job_id: str
    source_language: str
    target_language: str
    transcript_text: str
    translated_text: str
    summary_text: str = ""
    bilingual_text: str = ""
    original_txt_path: str = ""
    translation_txt_path: str = ""
    bilingual_txt_path: str = ""
    source_file_path: str = ""


@dataclass
class LiveState:
    is_active: bool = False
    mode: Optional[str] = None
    lang_a: Optional[str] = None
    lang_b: Optional[str] = None
    fixed_source_language: Optional[str] = None
    fixed_target_language: Optional[str] = None
    pending_original_text: Optional[str] = None
    pending_hint: Optional[str] = None


@dataclass
class LiveBuilder:
    mode: Optional[str] = None
    selecting: Optional[str] = None
    lang_a: Optional[str] = None
    lang_b: Optional[str] = None
    fixed_source_language: Optional[str] = None
    fixed_target_language: Optional[str] = None


@dataclass
class UserState:
    settings: UserSettings = field(default_factory=UserSettings)
    last_job: Optional[LastJob] = None
    live_state: LiveState = field(default_factory=LiveState)
    live_builder: LiveBuilder = field(default_factory=LiveBuilder)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "UserState":
        settings = UserSettings(**data.get("settings", {}))
        last_job_data = data.get("last_job")
        last_job = LastJob(**last_job_data) if last_job_data else None
        live_state = LiveState(**data.get("live_state", {}))
        live_builder = LiveBuilder(**data.get("live_builder", {}))
        return UserState(
            settings=settings,
            last_job=last_job,
            live_state=live_state,
            live_builder=live_builder,
        )
