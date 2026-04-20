from __future__ import annotations

from typing import Optional

import requests

from .languages import LanguageRegistry


class OllamaError(RuntimeError):
    pass


class OllamaTranslator:
    def __init__(
        self,
        base_url: str,
        translate_model: str,
        summary_model: str,
        registry: LanguageRegistry,
        correction_model: str | None = None,
    ) -> None:
        self.base_url = base_url
        self.translate_model = translate_model
        self.summary_model = summary_model
        self.correction_model = correction_model or translate_model
        self.registry = registry

    def _generate(self, model: str, prompt: str) -> str:
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=300,
        )
        if resp.status_code != 200:
            raise OllamaError(f"Ollama HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data.get("response", "").strip()

    def translate(self, text: str, source_language: Optional[str], target_language: str) -> str:
        src = self.registry.label(source_language) if source_language else "auto-detected source language"
        dst = self.registry.label(target_language)
        prompt = (
            f"Translate the following text from {src} to {dst}. "
            f"Keep the meaning natural. Preserve line breaks where possible. "
            f"Do not add commentary.\n\n{text}"
        )
        return self._generate(self.translate_model, prompt)

    def summarize(self, text: str, target_language: str) -> str:
        dst = self.registry.label(target_language)
        prompt = (
            f"Summarize the following transcript in {dst}. "
            f"Keep it concise and readable. No bullet spam.\n\n{text}"
        )
        return self._generate(self.summary_model, prompt)

    def correct_transcript(self, text: str, language: Optional[str]) -> str:
        if not text.strip():
            return text
        target = self.registry.label(language) if language else "the source language"
        prompt = (
            f"You are correcting automatic speech recognition output in {target}. "
            "Fix only likely transcription mistakes. Preserve the original meaning. "
            "Do not paraphrase. Do not add commentary. Return only the corrected text.\n\n"
            f"{text}"
        )
        corrected = self._generate(self.correction_model, prompt)
        return corrected or text
