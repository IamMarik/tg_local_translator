from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LanguageRegistry:
    def __init__(self, data_dir: Path) -> None:
        self._languages = json.loads((data_dir / "languages.json").read_text(encoding="utf-8"))
        self._aliases = json.loads((data_dir / "language_aliases.json").read_text(encoding="utf-8"))
        self._popular_pairs = json.loads((data_dir / "popular_live_pairs.json").read_text(encoding="utf-8"))
        emoji_path = data_dir / "language_emojis.json"
        self._emojis = json.loads(emoji_path.read_text(encoding="utf-8")) if emoji_path.exists() else {}
        self._by_code = {row["code"]: row["label"] for row in self._languages}

    @property
    def languages(self) -> list[dict[str, Any]]:
        return self._languages

    @property
    def popular_pairs(self) -> list[dict[str, str]]:
        return self._popular_pairs

    def resolve_code(self, raw: str | None) -> str | None:
        if not raw:
            return None
        value = raw.strip().lower()
        return self._aliases.get(value) or (value if value in self._by_code else None)

    def label(self, code: str | None) -> str:
        if not code:
            return "Unknown"
        return self._by_code.get(code, code)

    def emoji(self, code: str | None) -> str:
        if not code:
            return "🌐"
        return self._emojis.get(code.lower(), "🌐")

    def compact_label(self, code: str | None) -> str:
        if not code:
            return "🌐 --"
        normalized = code.lower()
        return f"{self.emoji(normalized)} {normalized.upper()}"

    def pair_label(self, left: str | None, right: str | None, arrow: str = "↔") -> str:
        return f"{self.compact_label(left)} {arrow} {self.compact_label(right)}"

    def locale_to_language(self, locale: str | None, default: str = "en") -> str:
        if not locale:
            return default
        base = locale.split("-")[0].split("_")[0].lower()
        return base if base in self._by_code else default

    def top_languages(self, include_auto: bool = False) -> list[dict[str, str]]:
        allowed = []
        for item in self._languages:
            if item["code"] == "auto" and not include_auto:
                continue
            if item["code"] in {"auto", "en", "ru", "vi", "de", "fr", "es", "ja"}:
                allowed.append(item)
        if include_auto and self._languages[0]["code"] == "auto":
            auto = self._languages[0]
            return [auto] + [x for x in allowed if x["code"] != "auto"]
        return allowed
