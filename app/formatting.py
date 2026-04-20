from __future__ import annotations

from pathlib import Path

from .languages import LanguageRegistry
from .models import LastJob



def preview_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."



def build_standard_message(job: LastJob, preview_chars: int) -> str:
    original = preview_text(job.transcript_text, preview_chars)
    translated = preview_text(job.translated_text, preview_chars)
    return (
        f"Оригинал:\n{original}\n\n"
        f"Перевод:\n{translated}\n\n"
        "Полные версии приложены файлами."
    )



def build_translation_only_message(job: LastJob, preview_chars: int) -> str:
    translated = preview_text(job.translated_text, preview_chars)
    return f"Перевод:\n{translated}\n\nПолная версия приложена файлом."



def build_original_only_message(job: LastJob, preview_chars: int) -> str:
    original = preview_text(job.transcript_text, preview_chars)
    return f"Оригинал:\n{original}\n\nПолная версия приложена файлом."



def build_summary_message(job: LastJob, preview_chars: int) -> str:
    summary = preview_text(job.summary_text or "Summary unavailable.", preview_chars)
    return f"Краткое содержание:\n{summary}"



def build_bilingual_text(job: LastJob) -> str:
    original_lines = [line.strip() for line in job.transcript_text.splitlines() if line.strip()]
    translated_lines = [line.strip() for line in job.translated_text.splitlines() if line.strip()]
    max_len = max(len(original_lines), len(translated_lines))
    chunks = []
    for i in range(max_len):
        left = original_lines[i] if i < len(original_lines) else ""
        right = translated_lines[i] if i < len(translated_lines) else ""
        chunks.append(f"Оригинал: {left}\nПеревод: {right}")
    return "\n\n".join(chunks).strip() or f"Оригинал: {job.transcript_text}\nПеревод: {job.translated_text}"



def build_live_message(source_language: str, target_language: str, original: str, translated: str, registry: LanguageRegistry) -> str:
    return (
        f"{registry.label(source_language)} -> {registry.label(target_language)}\n\n"
        f"Оригинал:\n{original}\n\n"
        f"Перевод:\n{translated}"
    )



def write_text_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
