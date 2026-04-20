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
    whisper_model_size: str
    default_ui_language: str
    max_file_size_mb: int
    preview_chars: int
    temp_dir: Path
    output_dir: Path
    storage_file: Path
    data_dir: Path



def load_config() -> AppConfig:
    root = Path(__file__).resolve().parent.parent
    temp_dir = root / os.getenv("TEMP_DIR", "temp")
    output_dir = root / os.getenv("OUTPUT_DIR", "outputs")
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required in .env")

    return AppConfig(
        bot_token=token,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_translate_model=os.getenv("OLLAMA_TRANSLATE_MODEL", "qwen2.5:7b"),
        ollama_summary_model=os.getenv("OLLAMA_SUMMARY_MODEL", "qwen2.5:7b"),
        whisper_model_size=os.getenv("WHISPER_MODEL_SIZE", "small"),
        default_ui_language=os.getenv("DEFAULT_UI_LANGUAGE", "ru"),
        max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "150")),
        preview_chars=int(os.getenv("PREVIEW_CHARS", "850")),
        temp_dir=temp_dir,
        output_dir=output_dir,
        storage_file=root / "storage" / "settings.json",
        data_dir=root / "data",
    )
