"""
Offline Speech-to-Text using OpenAI Whisper tiny model via faster-whisper.
No OpenAI API key required; runs fully locally.
"""
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_whisper_model = None


def _get_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            logger.info("Whisper tiny model loaded (CPU, int8)")
        except Exception as e:
            logger.warning("Failed to load Whisper model: %s", e)
            raise
    return _whisper_model


def _audio_path(data: bytes, content_type: Optional[str]) -> Path:
    """Save audio bytes to a temp file. Prefer .webm/.wav; faster-whisper/av can decode common formats."""
    ext = ".webm"
    if content_type:
        ct = content_type.lower().split(";")[0].strip()
        if "wav" in ct:
            ext = ".wav"
        elif "webm" in ct or "ogg" in ct:
            ext = ".webm"
        elif "mp3" in ct or "mpeg" in ct:
            ext = ".mp3"
    path = Path(tempfile.gettempdir()) / f"jarvis_voice_{id(data)}{ext}"
    path.write_bytes(data)
    return path


def _webm_to_wav_ffmpeg(path: Path) -> Optional[Path]:
    """Convert webm to wav using ffmpeg CLI if available. Returns wav path or None."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    out_path = path.with_suffix(".wav")
    try:
        kwargs = {"check": True, "capture_output": True, "timeout": 30}
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.run(
            [ffmpeg, "-y", "-i", str(path), "-acodec", "pcm_s16le", "-ar", "16000",
             "-ac", "1", str(out_path)],
            **kwargs,
        )
        path.unlink(missing_ok=True)
        return out_path
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("ffmpeg webm->wav failed: %s", e)
        return None


def _webm_to_wav(path: Path) -> Path:
    """Convert webm/ogg to wav. Tries PyAV first, then ffmpeg CLI. Returns wav path or original on failure."""
    try:
        import av
        out_path = path.with_suffix(".wav")
        with av.open(str(path), "r") as inp:
            in_stream = inp.streams.audio[0]
            sample_rate = in_stream.sample_rate or 48000
            with av.open(str(out_path), "w", format="wav") as out:
                out_stream = out.add_stream("pcm_s16le", rate=sample_rate)
                for frame in inp.decode(audio=0):
                    frame.pts = None
                    for packet in out_stream.encode(frame):
                        out.mux(packet)
                for packet in out_stream.encode(None):
                    out.mux(packet)
        path.unlink(missing_ok=True)
        return out_path
    except Exception as e:
        logger.warning("PyAV webm->wav failed: %s", e)
        wav_path = _webm_to_wav_ffmpeg(path)
        if wav_path is not None:
            return wav_path
        return path


def transcribe_audio(data: bytes, content_type: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Transcribe audio bytes to text using Whisper tiny (offline).
    Returns (text, language). text is normalized and stripped.
    """
    model = _get_model()
    path = None
    try:
        path = _audio_path(data, content_type)
        if not path.exists():
            return "", None
        to_transcribe = str(path)
        if path.suffix.lower() in (".webm", ".ogg"):
            wav_path = _webm_to_wav(path)
            if wav_path != path:
                path = wav_path
                to_transcribe = str(path)
        segments, info = model.transcribe(to_transcribe, beam_size=3, vad_filter=True)
        text_parts = [s.text.strip() for s in segments if s.text]
        text = " ".join(text_parts).strip()
        lang = getattr(info, "language", None)
        return text, lang
    except Exception as e:
        logger.warning("Whisper transcribe failed: %s", e)
        return "", None
    finally:
        if path and path.exists():
            try:
                path.unlink()
            except Exception:
                pass
