# Local Telegram Translator Bot

Локальный Telegram-бот для macOS:
- **File mode**: видео/аудио -> распознавание -> перевод -> превью + txt-файлы
- **Live translate**: voice/audio -> распознанный текст + перевод, без файлов
- запуск через **long polling**
- распознавание через **faster-whisper**
- перевод и summary через **Ollama**

## 1. Установка

```bash
brew install ffmpeg ollama
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Поднять Ollama

```bash
ollama serve
ollama pull qwen2.5:7b
```

При желании поменяй модель в `.env`.

## 3. Настроить бота

1. Создай бота через **BotFather**
2. Вставь токен в `.env`
3. Запусти:

```bash
python bot.py
```

## 4. Что умеет

### File mode
- поддерживает `video`, `audio`, `voice`, `document`
- режимы:
  - standard
  - translation_only
  - original_only
  - summary
  - bilingual

### Live translate
- **paired**: A <-> B
- **fixed**: A -> B
- популярные пары:
  - EN ↔ RU
  - VI ↔ RU
  - EN ↔ VI
- custom выбор языков

## 5. Как устроены данные

```text
storage/
  settings.json
  jobs.json
  live_state.json
data/
  languages.json
  language_aliases.json
  popular_live_pairs.json
```

## 6. Ограничения

- heavy STT и перевод идут локально, поэтому на длинных файлах будет заметная задержка
- diarization пока не включен
- live mode для MVP рассчитан на `voice` и `audio`, но обычные короткие видео/документы в file mode тоже принимаются

## 7. Дальше можно добавить

- SRT
- speaker diarization
- кэш по file_unique_id
- очередь задач
- историю live-сессий
