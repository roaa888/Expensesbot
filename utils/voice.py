"""
utils/voice.py
══════════════
STEP 1 of the voice pipeline:
  Telegram .ogg file  →  Whisper  →  transcribed text string

Dependencies:
  pip install openai-whisper pydub
  sudo apt install ffmpeg   (or brew install ffmpeg on Mac)
"""

import os
import tempfile
import logging

logger = logging.getLogger(__name__)

_whisper_model = None  # loaded once, cached


def _get_whisper(model_size: str = "base"):
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            logger.info(f"[Voice] Loading Whisper '{model_size}' (first-time download may take a moment)…")
            _whisper_model = whisper.load_model(model_size)
            logger.info("[Voice] ✅ Whisper model loaded")
        except ImportError:
            raise RuntimeError(
                "openai-whisper not installed.\n"
                "Run:  pip install openai-whisper"
            )
    return _whisper_model


async def transcribe_voice_message(bot, file_id: str, model_size: str = "base") -> str:
    """
    Download a Telegram voice/audio file and transcribe it.

    Returns the transcribed text string.
    Raises RuntimeError if whisper or ffmpeg is unavailable.
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        raise RuntimeError("pydub not installed.\nRun:  pip install pydub")

    with tempfile.TemporaryDirectory() as tmp:
        ogg_path = os.path.join(tmp, "voice.ogg")
        wav_path = os.path.join(tmp, "voice.wav")

        # 1. Download from Telegram
        tg_file = await bot.get_file(file_id)
        await tg_file.download_to_drive(ogg_path)
        logger.info(f"[Voice] ✅ Downloaded → {ogg_path}")

        # 2. Convert .ogg → .wav  (needs ffmpeg)
        try:
            audio = AudioSegment.from_ogg(ogg_path)
            audio.export(wav_path, format="wav")
        except Exception as e:
            raise RuntimeError(
                f"Audio conversion failed: {e}\n"
                "Make sure ffmpeg is installed:\n"
                "  Ubuntu:  sudo apt install ffmpeg\n"
                "  macOS:   brew install ffmpeg"
            )
        logger.info(f"[Voice] ✅ Converted → {wav_path}")

        # 3. Transcribe
        model = _get_whisper(model_size)
        result = model.transcribe(wav_path)
        text = result.get("text", "").strip()
        logger.info(f"[Voice] ✅ Transcript: {text!r}")
        return text


def detect_language(text: str) -> str:
    """
    Returns 'ar' if the text is predominantly Arabic characters, else 'en'.
    Works for pure Arabic, Arabizi (mixed), and pure English.
    """
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    return "ar" if (arabic_chars / max(len(text), 1)) > 0.15 else "en"
