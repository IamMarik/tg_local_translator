from __future__ import annotations

from pathlib import Path

from .languages import LanguageRegistry
from .models import LastJob



def preview_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."



def build_standard_message(job: LastJob, preview_chars: int, registry: LanguageRegistry) -> str:
    original = preview_text(job.transcript_text, preview_chars)
    translated = preview_text(job.translated_text, preview_chars)
    source = registry.compact_label(job.source_language)
    target = registry.compact_label(job.target_language)
    return (
        f"Оригинал {source}:\n{original}\n\n"
        f"Перевод {target}:\n{translated}\n\n"
        "Полные версии приложены файлами."
    )



def build_translation_only_message(job: LastJob, preview_chars: int, registry: LanguageRegistry) -> str:
    translated = preview_text(job.translated_text, preview_chars)
    target = registry.compact_label(job.target_language)
    return f"Перевод {target}:\n{translated}\n\nПолная версия приложена файлом."



def build_original_only_message(job: LastJob, preview_chars: int, registry: LanguageRegistry) -> str:
    original = preview_text(job.transcript_text, preview_chars)
    source = registry.compact_label(job.source_language)
    return f"Оригинал {source}:\n{original}\n\nПолная версия приложена файлом."



def build_summary_message(job: LastJob, preview_chars: int) -> str:
    summary = preview_text(job.summary_text or "Summary unavailable.", preview_chars)
    return f"Краткое содержание:\n{summary}"



def build_bilingual_text(job: LastJob, registry: LanguageRegistry) -> str:
    original_lines = [line.strip() for line in job.transcript_text.splitlines() if line.strip()]
    translated_lines = [line.strip() for line in job.translated_text.splitlines() if line.strip()]
    max_len = max(len(original_lines), len(translated_lines))
    chunks = []
    for i in range(max_len):
        left = original_lines[i] if i < len(original_lines) else ""
        right = translated_lines[i] if i < len(translated_lines) else ""
        chunks.append(
            f"Оригинал {registry.compact_label(job.source_language)}: {left}\n"
            f"Перевод {registry.compact_label(job.target_language)}: {right}"
        )
    return "\n\n".join(chunks).strip() or (
        f"Оригинал {registry.compact_label(job.source_language)}: {job.transcript_text}\n"
        f"Перевод {registry.compact_label(job.target_language)}: {job.translated_text}"
    )



def build_live_message(source_language: str, target_language: str, original: str, translated: str, registry: LanguageRegistry) -> str:
    return (
        f"🌐 Live: {registry.pair_label(source_language, target_language, '→')}\n\n"
        f"Оригинал {registry.compact_label(source_language)}:\n{original}\n\n"
        f"Перевод {registry.compact_label(target_language)}:\n{translated}"
    )



def write_text_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
