from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .languages import LanguageRegistry
from .models import FileMode


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Файл", callback_data="menu:open:file")],
        [InlineKeyboardButton("Live translate", callback_data="menu:open:live")],
        [InlineKeyboardButton("Язык перевода", callback_data="menu:open:lang")],
        [InlineKeyboardButton("Помощь", callback_data="menu:open:help")],
    ])


def file_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Режим файла", callback_data="file:open:mode")],
        [InlineKeyboardButton("Язык перевода", callback_data="file:open:lang")],
        [InlineKeyboardButton("Назад", callback_data="menu:back:home")],
    ])


def file_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    rows = []
    items = [
        ("Стандарт", FileMode.STANDARD.value),
        ("Только перевод", FileMode.TRANSLATION_ONLY.value),
        ("Только оригинал", FileMode.ORIGINAL_ONLY.value),
        ("Кратко", FileMode.SUMMARY.value),
        ("Построчно", FileMode.BILINGUAL.value),
    ]
    for title, value in items:
        prefix = "✅ " if current_mode == value else ""
        rows.append([InlineKeyboardButton(f"{prefix}{title}", callback_data=f"file_mode:set:{value}")])
    rows.append([InlineKeyboardButton("Назад", callback_data="menu:open:file")])
    return InlineKeyboardMarkup(rows)


def language_keyboard(registry: LanguageRegistry, callback_prefix: str, include_auto: bool = True) -> InlineKeyboardMarkup:
    rows = []
    top = registry.top_languages(include_auto=include_auto)
    for item in top:
        rows.append([InlineKeyboardButton(item["label"], callback_data=f"{callback_prefix}:{item['code']}")])
    rows.append([InlineKeyboardButton("Другой...", callback_data=f"{callback_prefix}:other")])
    rows.append([InlineKeyboardButton("Назад", callback_data="menu:back:home")])
    return InlineKeyboardMarkup(rows)


def live_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Парный", callback_data="live_mode:set:paired")],
        [InlineKeyboardButton("Жесткий", callback_data="live_mode:set:fixed")],
        [InlineKeyboardButton("Назад", callback_data="menu:back:home")],
    ])


def live_popular_pairs_keyboard(registry: LanguageRegistry, mode: str) -> InlineKeyboardMarkup:
    rows = []
    for pair in registry.popular_pairs:
        a, b = pair["a"], pair["b"]
        arrow = "↔" if mode == "paired" else "→"
        title = f"{registry.label(a)} {arrow} {registry.label(b)}"
        rows.append([InlineKeyboardButton(title, callback_data=f"live_pair:set:{a}:{b}")])
    rows.append([InlineKeyboardButton("Другие языки", callback_data="live_pair:custom:start")])
    rows.append([InlineKeyboardButton("Назад", callback_data="menu:open:live")])
    return InlineKeyboardMarkup(rows)


def live_active_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Сменить пару", callback_data="live:open:pair")],
        [InlineKeyboardButton("Выключить live", callback_data="live:stop:session")],
        [InlineKeyboardButton("Помощь", callback_data="menu:open:help")],
    ])


def file_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Кратко", callback_data="file_result:show:summary")],
        [InlineKeyboardButton("Построчно", callback_data="file_result:show:bilingual")],
        [InlineKeyboardButton("Стандарт", callback_data="file_result:show:standard")],
        [InlineKeyboardButton("Другой язык", callback_data="file_result:open:lang")],
        [InlineKeyboardButton("Повторить", callback_data="file_result:rerun:last")],
    ])


def live_force_language_keyboard(a: str, b: str, registry: LanguageRegistry) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Считать как {registry.label(a)}", callback_data=f"live:force_source:{a}")],
        [InlineKeyboardButton(f"Считать как {registry.label(b)}", callback_data=f"live:force_source:{b}")],
        [InlineKeyboardButton("Отмена", callback_data="live:cancel:force_source")],
    ])
