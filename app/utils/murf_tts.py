"""
Murf Stream Speech TTS: stream text to WAV file for daily brief and other voice output.
Uses Murf streaming API (PCM) and writes to WAV.
"""
import logging
import wave
from pathlib import Path
from typing import Iterable, Optional

import config

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2

DEFAULT_VOICE_ID = "Matthew"
DEFAULT_MODEL = "FALCON"
DEFAULT_LOCALE = "en-US"


def _get_client():
    """Lazy Murf client (only when API key is set)."""
    if not config.MURF_API_KEY:
        return None
    try:
        from murf import Murf, MurfRegion
        region_map = {
            "GLOBAL": MurfRegion.GLOBAL,
            "India": MurfRegion.IN,
            "US-EAST": MurfRegion.US_EAST,
            "US_WEST": MurfRegion.US_WEST,
            "Europe": MurfRegion.EU_CENTRAL,
            "Japan": MurfRegion.JP,
            "Australia": MurfRegion.AU,
            "Korea": MurfRegion.KR,
            "Middle East": MurfRegion.ME,
            "South America": MurfRegion.SA_EAST,
            "UK": MurfRegion.UK,
            "Canada": MurfRegion.CA,
        }
        region = region_map.get(config.MURF_REGION, MurfRegion.GLOBAL)
        return Murf(api_key=config.MURF_API_KEY, region=region)
    except Exception as e:
        logger.warning("Murf client init failed: %s", e)
        return None


def stream_to_wav(
    audio_stream: Iterable[bytes],
    path: str | Path,
    sample_rate: int = SAMPLE_RATE,
) -> str:
    """Write PCM stream to WAV file. Returns path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH_BYTES)
        wf.setframerate(sample_rate)
        for chunk in audio_stream:
            wf.writeframes(chunk)
    return str(path)


def text_to_speech_wav(
    text: str,
    output_path: str | Path,
    voice_id: str = DEFAULT_VOICE_ID,
    model: str = DEFAULT_MODEL,
    locale: str = DEFAULT_LOCALE,
    style: Optional[str] = "Conversation",
    sample_rate: int = SAMPLE_RATE,
) -> Optional[str]:
    """
    Convert text to speech using Murf streaming API and save as WAV.
    Returns path to WAV file, or None if API key missing or request failed.
    """
    if not text or not text.strip():
        return None
    client = _get_client()
    if not client:
        return None
    try:
        audio_stream = client.text_to_speech.stream(
            text=text.strip(),
            voice_id=voice_id,
            model=model,
            multi_native_locale=locale,
            sample_rate=sample_rate,
            format="PCM",
            style=style or None,
        )
        return stream_to_wav(audio_stream, output_path, sample_rate)
    except Exception as e:
        logger.warning("Murf TTS failed: %s", e)
        return None
