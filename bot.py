from __future__ import annotations

import asyncio
import difflib
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import load_config
from app.formatting import (
    build_bilingual_text,
    build_live_message,
    build_original_only_message,
    build_standard_message,
    build_summary_message,
    build_translation_only_message,
    write_text_file,
)
from app.keyboards import (
    file_menu_keyboard,
    file_mode_keyboard,
    file_result_keyboard,
    home_keyboard,
    language_keyboard,
    live_active_keyboard,
    live_force_language_keyboard,
    live_mode_keyboard,
    live_popular_pairs_keyboard,
)
from app.languages import LanguageRegistry
from app.media import MediaError, extract_audio_to_wav
from app.models import FileMode, LastJob, LiveBuilder, LiveMode, UserState
from app.state_helpers import resolve_target_language
from app.storage import JsonStorage
from app.transcribe import Transcriber, TranscriptionResult
from app.translate import OllamaError, OllamaTranslator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG = load_config()
REGISTRY = LanguageRegistry(CONFIG.data_dir)
STORAGE = JsonStorage(CONFIG.storage_file)
FILE_TRANSCRIBER = Transcriber(
    CONFIG.whisper_model_size_file,
    compute_type=CONFIG.whisper_compute_type,
)
LIVE_TRANSCRIBER = Transcriber(
    CONFIG.whisper_model_size_live,
    compute_type=CONFIG.whisper_compute_type,
)
TRANSLATOR = OllamaTranslator(
    CONFIG.ollama_base_url,
    CONFIG.ollama_translate_model,
    CONFIG.ollama_summary_model,
    REGISTRY,
    correction_model=CONFIG.ollama_correction_model,
)


def normalized_change_ratio(before: str, after: str) -> float:
    if not before and not after:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, before or "", after or "").ratio()


def is_low_confidence_transcript(result: TranscriptionResult, source_language: Optional[str] = None) -> bool:
    text = (result.text or "").strip()
    language = source_language or result.language

    if not text:
        return True
    if len(text) < 6:
        return True
    if result.no_speech_prob > 0.6:
        return True
    if language == "vi" and result.language_probability < 0.7:
        return True
    if result.avg_logprob < -1.0:
        return True
    if result.compression_ratio > 2.4:
        return True
    return False


def maybe_correct_transcript(result: TranscriptionResult, source_language: Optional[str] = None, always_for_file: bool = False) -> str:
    text = result.text
    language = source_language or result.language

    if not text or not CONFIG.enable_stt_correction:
        return text
    if language != "vi":
        return text

    should_run_first_pass = always_for_file or is_low_confidence_transcript(result, source_language=language)
    if not should_run_first_pass:
        return text

    try:
        corrected = TRANSLATOR.correct_transcript(text, language)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Transcript correction failed on first pass: %s", exc)
        return text

    if not corrected:
        return text

    if is_low_confidence_transcript(result, source_language=language) and normalized_change_ratio(text, corrected) < 0.03:
        try:
            corrected_second = TRANSLATOR.correct_transcript(corrected, language, second_pass=True)
            if corrected_second:
                corrected = corrected_second
        except Exception as exc:  # noqa: BLE001
            logger.warning("Transcript correction failed on second pass: %s", exc)

    return corrected


# ---------- texts ----------

def home_text(state: UserState) -> str:
    target = resolve_target_language(state, None, REGISTRY) if state.settings.target_language_source == "manual" else state.settings.target_language
    lines = [
        "Выбери сценарий:",
        "- Файл: обработка видео и аудио с полными текстами",
        "- Live translate: быстрый перевод голосовых сообщений без файлов",
        "",
        f"Режим файла: {state.settings.file_mode}",
        f"Язык перевода: {REGISTRY.compact_label(target)}",
    ]
    if state.live_state.is_active:
        if state.live_state.mode == LiveMode.FIXED.value:
            lines.extend(["", f"Live статус: {REGISTRY.pair_label(state.live_state.fixed_source_language, state.live_state.fixed_target_language, '→')}"])
        else:
            lines.extend(["", f"Live статус: {REGISTRY.pair_label(state.live_state.lang_a, state.live_state.lang_b, '↔')}"])
    return "\n".join(lines)


def file_menu_text(state: UserState) -> str:
    return (
        "Отправь видео или аудио.\n"
        "По умолчанию я пришлю:\n"
        "- превью оригинала\n"
        "- превью перевода\n"
        "- полные тексты файлами\n\n"
        f"Текущий режим: {state.settings.file_mode}"
    )


def help_text() -> str:
    return (
        "Поддерживаемые форматы: mp4, mov, m4a, mp3, wav, ogg.\n"
        "Можно отправлять как video, audio, voice или document.\n"
        "Live translate рассчитан на voice/audio.\n"
        "Язык речи определяется автоматически в paired live mode."
    )


# ---------- helpers ----------

def get_state(user_id: int) -> UserState:
    state = STORAGE.get_user_state(user_id)
    if not state.settings.ui_language:
        state.settings.ui_language = CONFIG.default_ui_language
    if not state.settings.target_language:
        state.settings.target_language = CONFIG.default_ui_language
    return state


def save_state(user_id: int, state: UserState) -> None:
    STORAGE.save_user_state(user_id, state)


def target_language_for_user(state: UserState, telegram_locale: Optional[str]) -> str:
    return resolve_target_language(state, telegram_locale, REGISTRY)


def is_supported_media(filename: str) -> bool:
    suffix = Path(filename.lower()).suffix
    return suffix in {".mp4", ".mov", ".m4a", ".mp3", ".wav", ".ogg", ".aac"}


async def show_typing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)


async def render_home(update: Update, state: UserState, edit: bool = False) -> None:
    text = home_text(state)
    keyboard = home_keyboard()
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.effective_message.reply_text(text, reply_markup=keyboard)


async def render_file_menu(update: Update, state: UserState, edit: bool = True) -> None:
    text = file_menu_text(state)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=file_menu_keyboard())
    else:
        await update.effective_message.reply_text(text, reply_markup=file_menu_keyboard())


async def send_error(update: Update, text: str) -> None:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=home_keyboard())
    else:
        await update.effective_message.reply_text(text, reply_markup=home_keyboard())




def reset_transient_state(state: UserState) -> None:
    state.live_builder = LiveBuilder()
    state.live_state.pending_original_text = None
    state.live_state.pending_hint = None


def humanize_processing_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()

    if "model is not supported by your version of ollama" in lowered:
        return (
            "Текущая версия Ollama слишком старая для выбранной модели.\n"
            "Обнови Ollama или укажи более простую локальную модель в .env.\n\n"
            f"Техническая деталь: {message}"
        )
    if "not found" in lowered and "model" in lowered:
        return (
            "Указанная модель Ollama не найдена локально.\n"
            "Проверь имя модели в .env и скачай её через ollama pull.\n\n"
            f"Техническая деталь: {message}"
        )
    if "ollama http 500" in lowered:
        return (
            "Ollama вернула внутреннюю ошибку.\n"
            "Часто помогает обновить Ollama или сменить модель в .env.\n\n"
            f"Техническая деталь: {message}"
        )

    return message


async def reply_with_home(message: Message, text: str) -> None:
    await message.reply_text(text, reply_markup=home_keyboard())


async def send_processing_error(update: Update, state: UserState, exc: Exception) -> None:
    reset_transient_state(state)
    save_state(update.effective_user.id, state)
    await reply_with_home(update.effective_message, f"Ошибка обработки:\n{humanize_processing_error(exc)}")


def build_status_text(stage: str) -> str:
    return f"Файл принят.\n{stage}"


async def download_telegram_file(update: Update, context: ContextTypes.DEFAULT_TYPE, dest_path: Path) -> Path:
    message = update.effective_message
    file_obj = None
    filename = dest_path.name

    if message.video:
        file_obj = message.video
        if getattr(message.video, "file_name", None):
            filename = message.video.file_name
    elif message.audio:
        file_obj = message.audio
        if getattr(message.audio, "file_name", None):
            filename = message.audio.file_name
    elif message.voice:
        file_obj = message.voice
        filename = f"voice_{dest_path.stem}.ogg"
    elif message.document:
        file_obj = message.document
        filename = message.document.file_name or filename

    if file_obj is None:
        raise RuntimeError("Unsupported telegram file type")

    final_path = dest_path.with_name(filename)
    tg_file = await context.bot.get_file(file_obj.file_id)
    await tg_file.download_to_drive(custom_path=str(final_path))
    return final_path


def process_file_pipeline(input_path: Path, state: UserState, telegram_locale: Optional[str], user_id: int) -> LastJob:
    audio_path = CONFIG.temp_dir / f"{uuid.uuid4().hex}.wav"
    extract_audio_to_wav(input_path, audio_path, audio_filter=CONFIG.audio_filter or None)
    file_result = FILE_TRANSCRIBER.transcribe_result(audio_path)
    if file_result.language == "vi":
        file_result = FILE_TRANSCRIBER.transcribe_result(audio_path, language="vi")
    source_language = file_result.language
    transcript_text = maybe_correct_transcript(file_result, source_language=source_language, always_for_file=True)
    if not transcript_text:
        raise RuntimeError("Не удалось распознать речь")

    target_language = target_language_for_user(state, telegram_locale)
    translated_text = TRANSLATOR.translate(transcript_text, source_language, target_language)
    summary_text = TRANSLATOR.summarize(translated_text or transcript_text, target_language)
    bilingual_text = build_bilingual_text(
        LastJob(
            job_id="temp",
            source_language=source_language or "auto",
            target_language=target_language,
            transcript_text=transcript_text,
            translated_text=translated_text,
        )
    )

    out_dir = CONFIG.output_dir / str(user_id) / uuid.uuid4().hex
    original_txt = write_text_file(out_dir / "original.txt", transcript_text)
    translation_txt = write_text_file(out_dir / "translation.txt", translated_text)
    bilingual_txt = write_text_file(out_dir / "bilingual.txt", bilingual_text)

    return LastJob(
        job_id=uuid.uuid4().hex,
        source_language=source_language or "auto",
        target_language=target_language,
        transcript_text=transcript_text,
        translated_text=translated_text,
        summary_text=summary_text,
        bilingual_text=bilingual_text,
        original_txt_path=str(original_txt),
        translation_txt_path=str(translation_txt),
        bilingual_txt_path=str(bilingual_txt),
        source_file_path=str(input_path),
    )


def process_live_pipeline(input_path: Path, state: UserState) -> tuple[str, str, str, Optional[str]]:
    audio_path = CONFIG.temp_dir / f"{uuid.uuid4().hex}.wav"
    extract_audio_to_wav(input_path, audio_path, audio_filter=CONFIG.audio_filter or None)

    live = state.live_state
    if live.mode == LiveMode.FIXED.value:
        live_result = LIVE_TRANSCRIBER.transcribe_result(audio_path, language=live.fixed_source_language)
        source_language = live.fixed_source_language or "en"
        original_text = maybe_correct_transcript(live_result, source_language=source_language)
        target_language = live.fixed_target_language or "en"
        translated = TRANSLATOR.translate(original_text, source_language, target_language)
        return source_language, target_language, original_text, translated

    live_result = LIVE_TRANSCRIBER.transcribe_result(audio_path, language=None)
    detected = live_result.language
    original_text = maybe_correct_transcript(live_result, source_language=detected)
    a = live.lang_a or "en"
    b = live.lang_b or "ru"
    if detected not in {a, b}:
        return "", "", original_text, None
    source_language = detected
    target_language = b if detected == a else a
    translated = TRANSLATOR.translate(original_text, source_language, target_language)
    return source_language, target_language, original_text, translated


async def send_file_mode_result(update: Update, context: ContextTypes.DEFAULT_TYPE, state: UserState) -> None:
    job = state.last_job
    if not job:
        await send_error(update, "Сначала отправь видео или аудио.")
        return

    mode = state.settings.file_mode
    if mode == FileMode.STANDARD.value:
        message = build_standard_message(job, CONFIG.preview_chars, REGISTRY)
        files = [job.original_txt_path, job.translation_txt_path]
    elif mode == FileMode.TRANSLATION_ONLY.value:
        message = build_translation_only_message(job, CONFIG.preview_chars, REGISTRY)
        files = [job.translation_txt_path]
    elif mode == FileMode.ORIGINAL_ONLY.value:
        message = build_original_only_message(job, CONFIG.preview_chars, REGISTRY)
        files = [job.original_txt_path]
    elif mode == FileMode.SUMMARY.value:
        message = build_summary_message(job, CONFIG.preview_chars)
        files = [job.translation_txt_path] if job.translation_txt_path else []
    else:
        bilingual_preview = job.bilingual_text[: CONFIG.preview_chars] + ("..." if len(job.bilingual_text) > CONFIG.preview_chars else "")
        message = f"Построчно:\n{bilingual_preview}\n\nПолная версия приложена файлом."
        files = [job.bilingual_txt_path]

    await update.effective_message.reply_text(message, reply_markup=file_result_keyboard())
    for path in files:
        if path and Path(path).exists():
            with open(path, "rb") as f:
                await update.effective_message.reply_document(f)


# ---------- command handlers ----------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    state = get_state(user.id)
    locale = user.language_code if user else None
    if state.settings.target_language_source != "manual":
        state.settings.target_language = REGISTRY.locale_to_language(locale, default=CONFIG.default_ui_language)
    save_state(user.id, state)
    await render_home(update, state, edit=False)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(help_text(), reply_markup=home_keyboard())


# ---------- callback routing ----------
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    state = get_state(user_id)
    data = query.data or ""

    if data in {"menu:back:home", "menu:home"}:
        await render_home(update, state, edit=True)
        return
    if data == "menu:open:file":
        await render_file_menu(update, state, edit=True)
        return
    if data == "menu:open:live":
        await query.edit_message_text("Выбери режим live translate", reply_markup=live_mode_keyboard())
        return
    if data == "menu:open:lang":
        await query.edit_message_text(
            "Выбери язык перевода",
            reply_markup=language_keyboard(REGISTRY, "lang:set", include_auto=True),
        )
        return
    if data == "menu:open:help":
        await query.edit_message_text(help_text(), reply_markup=home_keyboard())
        return

    if data == "file:open:mode":
        await query.edit_message_text(
            "Выбери, как показывать результат.",
            reply_markup=file_mode_keyboard(state.settings.file_mode),
        )
        return
    if data == "file:open:lang":
        await query.edit_message_text(
            "Выбери язык перевода",
            reply_markup=language_keyboard(REGISTRY, "lang:set", include_auto=True),
        )
        return

    if data.startswith("file_mode:set:"):
        state.settings.file_mode = data.split(":", 2)[2]
        save_state(user_id, state)
        await render_file_menu(update, state, edit=True)
        return

    if data.startswith("lang:set:"):
        value = data.split(":", 2)[2]
        if value == "other":
            await query.message.reply_text("Пока здесь сделан быстрый выбор из основных языков. Остальные добавь в data/languages.json.")
            return
        if value == "auto":
            state.settings.target_language_source = "telegram_locale"
            state.settings.target_language = REGISTRY.locale_to_language(update.effective_user.language_code, default="en")
        else:
            state.settings.target_language_source = "manual"
            state.settings.target_language = value
        save_state(user_id, state)
        await render_home(update, state, edit=True)
        return

    if data.startswith("file_result:show:"):
        mode = data.split(":", 2)[2]
        state.settings.file_mode = mode
        save_state(user_id, state)
        await query.message.reply_text("Режим обновлен для последнего результата.")
        await send_file_mode_result(update, context, state)
        return

    if data == "file_result:open:lang":
        rows = []
        for item in REGISTRY.top_languages(include_auto=False)[:6]:
            rows.append([InlineKeyboardButton(item["label"], callback_data=f"file_result:translate:{item['code']}")])
        rows.append([
            InlineKeyboardButton("⬅️ К результату", callback_data="file_result:back:last"),
            InlineKeyboardButton("🏠 Домой", callback_data="menu:home"),
        ])
        await query.edit_message_text("Выбери новый язык для последнего результата", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("file_result:translate:"):
        job = state.last_job
        if not job:
            await send_error(update, "Сначала отправь файл.")
            return
        target_language = data.split(":", 2)[2]
        translated = await asyncio.to_thread(TRANSLATOR.translate, job.transcript_text, job.source_language, target_language)
        job.target_language = target_language
        job.translated_text = translated
        job.summary_text = await asyncio.to_thread(TRANSLATOR.summarize, translated, target_language)
        job.bilingual_text = build_bilingual_text(job, REGISTRY)
        write_text_file(Path(job.translation_txt_path), translated)
        write_text_file(Path(job.bilingual_txt_path), job.bilingual_text)
        state.last_job = job
        save_state(user_id, state)
        await query.message.reply_text(f"Перевод обновлен: {REGISTRY.label(target_language)}")
        await send_file_mode_result(update, context, state)
        return

    if data in {"file_result:rerun:last", "file_result:back:last"}:
        if not state.last_job:
            await send_error(update, "Сначала отправь файл.")
            return
        await send_file_mode_result(update, context, state)
        return

    if data.startswith("live_mode:set:"):
        mode = data.split(":", 2)[2]
        state.live_builder = LiveBuilder(mode=mode)
        save_state(user_id, state)
        await query.edit_message_text(
            "Выбери пару или перейди к выбору языков.",
            reply_markup=live_popular_pairs_keyboard(REGISTRY, mode),
        )
        return

    if data.startswith("live_pair:set:"):
        _, _, a, b = data.split(":")
        mode = state.live_builder.mode or LiveMode.PAIRED.value
        if mode == LiveMode.PAIRED.value:
            state.live_state.is_active = True
            state.live_state.mode = LiveMode.PAIRED.value
            state.live_state.lang_a = a
            state.live_state.lang_b = b
            state.live_state.fixed_source_language = None
            state.live_state.fixed_target_language = None
            save_state(user_id, state)
            await query.edit_message_text(
                f"Live translate включен:\n\n{REGISTRY.pair_label(a, b, '↔')}\n\nОтправляй voice или audio.",
                reply_markup=live_active_keyboard(),
            )
        else:
            state.live_state.is_active = True
            state.live_state.mode = LiveMode.FIXED.value
            state.live_state.fixed_source_language = a
            state.live_state.fixed_target_language = b
            state.live_state.lang_a = a
            state.live_state.lang_b = b
            save_state(user_id, state)
            await query.edit_message_text(
                f"Live translate включен:\n\n{REGISTRY.pair_label(a, b, '→')}\n\nОтправляй voice или audio.",
                reply_markup=live_active_keyboard(),
            )
        return

    if data == "live_pair:custom:start":
        builder = state.live_builder
        if builder.mode == LiveMode.FIXED.value:
            builder.selecting = "fixed_source"
            save_state(user_id, state)
            await query.edit_message_text(
                "Выбери язык, с которого переводим",
                reply_markup=language_keyboard(REGISTRY, "live_fixed_src:set", include_auto=True),
            )
        else:
            builder.selecting = "lang_a"
            save_state(user_id, state)
            await query.edit_message_text(
                "Выбери первый язык",
                reply_markup=language_keyboard(REGISTRY, "live_pair_custom:set_a", include_auto=True),
            )
        return

    if data.startswith("live_fixed_src:set:"):
        value = data.split(":", 2)[2]
        if value == "other":
            await query.message.reply_text("Добавь язык в data/languages.json и aliases в data/language_aliases.json.")
            return
        if value == "auto":
            value = REGISTRY.locale_to_language(update.effective_user.language_code, default="en")
        state.live_builder.fixed_source_language = value
        save_state(user_id, state)
        await query.edit_message_text(
            "Выбери язык, на который переводим",
            reply_markup=language_keyboard(REGISTRY, "live_fixed_dst:set", include_auto=True),
        )
        return

    if data.startswith("live_fixed_dst:set:"):
        value = data.split(":", 2)[2]
        if value == "other":
            await query.message.reply_text("Добавь язык в data/languages.json и aliases в data/language_aliases.json.")
            return
        if value == "auto":
            value = REGISTRY.locale_to_language(update.effective_user.language_code, default="en")
        src = state.live_builder.fixed_source_language
        if src == value:
            await query.message.reply_text("Ты выбрал одинаковые языки. Сменить языки лучше перед стартом.")
            return
        state.live_state.is_active = True
        state.live_state.mode = LiveMode.FIXED.value
        state.live_state.fixed_source_language = src
        state.live_state.fixed_target_language = value
        state.live_state.lang_a = src
        state.live_state.lang_b = value
        save_state(user_id, state)
        await query.edit_message_text(
            f"Live translate включен:\n\n{REGISTRY.pair_label(src, value, '→')}\n\nОтправляй voice или audio.",
            reply_markup=live_active_keyboard(),
        )
        return

    if data.startswith("live_pair_custom:set_a:"):
        value = data.split(":", 2)[2]
        if value == "other":
            await query.message.reply_text("Добавь язык в data/languages.json и aliases в data/language_aliases.json.")
            return
        if value == "auto":
            value = REGISTRY.locale_to_language(update.effective_user.language_code, default="en")
        state.live_builder.lang_a = value
        save_state(user_id, state)
        await query.edit_message_text(
            "Выбери второй язык",
            reply_markup=language_keyboard(REGISTRY, "live_pair_custom:set_b", include_auto=False),
        )
        return

    if data.startswith("live_pair_custom:set_b:"):
        value = data.split(":", 2)[2]
        if value == "other":
            await query.message.reply_text("Добавь язык в data/languages.json и aliases в data/language_aliases.json.")
            return
        a = state.live_builder.lang_a
        b = REGISTRY.locale_to_language(update.effective_user.language_code, default="en") if value == "auto" else value
        if a == b:
            await query.message.reply_text("Для парного режима выбери два разных языка.")
            return
        state.live_state.is_active = True
        state.live_state.mode = LiveMode.PAIRED.value
        state.live_state.lang_a = a
        state.live_state.lang_b = b
        save_state(user_id, state)
        await query.edit_message_text(
            f"Live translate включен:\n\n{REGISTRY.pair_label(a, b, '↔')}\n\nОтправляй voice или audio.",
            reply_markup=live_active_keyboard(),
        )
        return

    if data == "live:open:pair":
        await query.edit_message_text("Выбери режим live translate", reply_markup=live_mode_keyboard())
        return

    if data == "live:stop:session":
        state.live_state.is_active = False
        reset_transient_state(state)
        save_state(user_id, state)
        await query.edit_message_text("Live translate выключен.", reply_markup=home_keyboard())
        return

    if data.startswith("live:force_source:"):
        forced = data.split(":", 2)[2]
        original_text = state.live_state.pending_original_text
        if not original_text:
            await send_error(update, "Нет ожидающего сообщения для повторного выбора языка.")
            return
        a = state.live_state.lang_a or "en"
        b = state.live_state.lang_b or "ru"
        target = b if forced == a else a
        translated = await asyncio.to_thread(TRANSLATOR.translate, original_text, forced, target)
        state.live_state.pending_original_text = None
        state.live_state.pending_hint = None
        save_state(user_id, state)
        await query.message.reply_text(build_live_message(forced, target, original_text, translated, REGISTRY), reply_markup=live_active_keyboard())
        return

    if data == "live:cancel:force_source":
        state.live_state.pending_original_text = None
        state.live_state.pending_hint = None
        save_state(user_id, state)
        await query.message.reply_text("Отменено.", reply_markup=live_active_keyboard())
        return

    await send_error(update, "Неизвестное действие.")


# ---------- media handlers ----------
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    state = get_state(user.id)
    message = update.effective_message

    if message.document and message.document.file_name and not is_supported_media(message.document.file_name):
        await reply_with_home(message, "Не удалось обработать файл. Отправь mp4, mov, m4a, mp3, wav, ogg или aac.")
        return

    max_bytes = CONFIG.max_file_size_mb * 1024 * 1024
    size = 0
    for candidate in [message.video, message.audio, message.voice, message.document]:
        if candidate and getattr(candidate, "file_size", None):
            size = candidate.file_size
            break
    if size and size > max_bytes:
        await reply_with_home(message, "Файл слишком большой для текущего локального режима.")
        return

    status = await message.reply_text(build_status_text("Скачиваю файл..."))
    temp_base = CONFIG.temp_dir / uuid.uuid4().hex
    input_path = await download_telegram_file(update, context, temp_base)

    try:
        if state.live_state.is_active and (message.voice or message.audio):
            await status.edit_text(build_status_text("Распознаю live-сообщение..."))
            source, target, original, translated = await asyncio.to_thread(process_live_pipeline, input_path, state)
            if translated is None:
                state.live_state.pending_original_text = original
                save_state(user.id, state)
                await status.edit_text(
                    "Не удалось уверенно определить язык сообщения.\n\n"
                    f"Распознанный текст:\n{original}",
                    reply_markup=live_force_language_keyboard(state.live_state.lang_a or "en", state.live_state.lang_b or "ru", REGISTRY),
                )
                return
            await status.delete()
            await message.reply_text(build_live_message(source, target, original, translated, REGISTRY), reply_markup=live_active_keyboard())
            return

        await status.edit_text(build_status_text("Извлекаю аудио..."))
        await status.edit_text(build_status_text("Распознаю речь..."))
        job = await asyncio.to_thread(process_file_pipeline, input_path, state, user.language_code, user.id)
        state.last_job = job
        save_state(user.id, state)
        await status.edit_text(build_status_text("Формирую результат..."))
        await status.delete()
        await send_file_mode_result(update, context, state)
    except (MediaError, OllamaError, RuntimeError) as exc:
        logger.exception("Processing failed")
        try:
            await status.delete()
        except Exception:
            pass
        await send_processing_error(update, state, exc)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Отправь видео, аудио или voice. Для навигации используй /start.",
        reply_markup=home_keyboard(),
    )


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled telegram error", exc_info=context.error)

    if not isinstance(update, Update) or update.effective_user is None or update.effective_message is None:
        return

    state = get_state(update.effective_user.id)
    exc = context.error if isinstance(context.error, Exception) else RuntimeError(str(context.error))
    await send_processing_error(update, state, exc)



def main() -> None:
    application = Application.builder().token(CONFIG.bot_token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(callback_router))
    media_filter = filters.VIDEO | filters.AUDIO | filters.VOICE | filters.Document.ALL
    application.add_handler(MessageHandler(media_filter, handle_media))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(global_error_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
