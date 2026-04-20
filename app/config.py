from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    bot_token: str
    ollama_base_url: str
    ollama_translate_model: str
    ollama_summary_model: str
    ollama_correction_model: str
    whisper_model_size: str
    whisper_model_size_file: str
    whisper_model_size_live: str
    whisper_compute_type: str
    default_ui_language: str
    max_file_size_mb: int
    preview_chars: int
    temp_dir: Path
    output_dir: Path
    storage_file: Path
    data_dir: Path
    audio_filter: str
    enable_stt_correction: bool


def load_config() -> AppConfig:
    root = Path(__file__).resolve().parent.parent
    temp_dir = root / os.getenv("TEMP_DIR", "temp")
    output_dir = root / os.getenv("OUTPUT_DIR", "outputs")
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required in .env")

    translate_model = os.getenv("OLLAMA_TRANSLATE_MODEL", "translategemma")

    return AppConfig(
        bot_token=token,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_translate_model=translate_model,
        ollama_summary_model=os.getenv("OLLAMA_SUMMARY_MODEL", translate_model),
        ollama_correction_model=os.getenv("OLLAMA_CORRECTION_MODEL", translate_model),
        whisper_model_size=os.getenv("WHISPER_MODEL_SIZE", "small"),
        whisper_model_size_file=os.getenv("WHISPER_MODEL_SIZE_FILE", os.getenv("WHISPER_MODEL_SIZE", "small")),
        whisper_model_size_live=os.getenv("WHISPER_MODEL_SIZE_LIVE", os.getenv("WHISPER_MODEL_SIZE", "small")),
        whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        default_ui_language=os.getenv("DEFAULT_UI_LANGUAGE", "ru"),
        max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "150")),
        preview_chars=int(os.getenv("PREVIEW_CHARS", "850")),
        temp_dir=temp_dir,
        output_dir=output_dir,
        storage_file=root / "storage" / "settings.json",
        data_dir=root / "data",
        audio_filter=os.getenv("AUDIO_FILTER", "").strip(),
        enable_stt_correction=os.getenv("ENABLE_STT_CORRECTION", "true").lower() == "true",
    )
