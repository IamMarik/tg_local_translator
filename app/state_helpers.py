from __future__ import annotations

from .languages import LanguageRegistry
from .models import UserState


def resolve_target_language(
    state: UserState, telegram_language_code: str | None, registry: LanguageRegistry
) -> str:
    if state.settings.target_language_source == "manual":
        return state.settings.target_language
    return registry.locale_to_language(
        telegram_language_code, default=state.settings.target_language or "en"
    )
