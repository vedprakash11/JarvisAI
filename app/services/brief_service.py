"""
Daily brief: weather (OpenWeatherMap) + headlines (Tavily) + upcoming reminders only +
"What happened today" (previous/sent reminders) + time + optional learning summary.
Produces short "Good morning" text and optional Murf TTS WAV.
"""
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import config
from app.utils.time_info import get_today_phrase, get_current_datetime_str
from app.utils.weather import get_weather_openweathermap
from app.services.realtime_service import search_tavily
from app.services.groq_service import GroqService
from app.utils.murf_tts import text_to_speech_wav
from app.core.settings import get_settings
from app.db import get_upcoming_reminders_for_user, get_sent_reminders_today_for_user

logger = logging.getLogger(__name__)


def _learning_data_summary(max_chars: int = 1500) -> str:
    """First portion of learning_data .txt files for brief context."""
    try:
        learning_dir = get_settings().learning_data_dir
        if not learning_dir.exists():
            return ""
        parts = []
        total = 0
        for f in sorted(learning_dir.glob("*.txt")):
            if total >= max_chars:
                break
            try:
                text = f.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    take = min(len(text), max_chars - total)
                    parts.append(text[:take] + ("..." if len(text) > take else ""))
                    total += take
            except Exception:
                continue
        return "\n\n".join(parts) if parts else ""
    except Exception as e:
        logger.debug("Learning data summary failed: %s", e)
        return ""


def _format_reminder(r: dict) -> str:
    """Format a reminder dict for brief text (message + run_at time)."""
    msg = (r.get("message") or "").strip()
    run_at = r.get("run_at")
    if run_at:
        if hasattr(run_at, "strftime"):
            time_str = run_at.strftime("%H:%M")
        else:
            time_str = str(run_at)[:16]
        return f"- {msg} (at {time_str})" if msg else ""
    return f"- {msg}" if msg else ""


def generate_brief_text(
    user_id: Optional[int] = None,
    user_name: Optional[str] = None,
    city: Optional[str] = None,
    include_headlines: bool = True,
    include_learning: bool = True,
) -> str:
    """
    Build weather + headlines + upcoming reminders only + "What happened today" (sent reminders)
    + time, then LLM to produce a short "Good morning" brief.
    """
    today_phrase = get_today_phrase()
    time_info = get_current_datetime_str()
    weather = get_weather_openweathermap(city or config.OPENWEATHERMAP_DEFAULT_CITY)
    headlines = ""
    if include_headlines and config.TAVILY_API_KEY:
        headlines = search_tavily("top headlines news today", max_results=5)
    learning = _learning_data_summary() if include_learning else ""

    upcoming_lines = []
    previous_lines = []
    if user_id is not None:
        for r in get_upcoming_reminders_for_user(user_id, limit=20):
            line = _format_reminder(r)
            if line:
                upcoming_lines.append(line)
        for r in get_sent_reminders_today_for_user(user_id):
            line = _format_reminder(r)
            if line:
                previous_lines.append(line)

    user_label = (user_name or config.USER_NAME or "there").strip() or "there"
    system = f"""You are {config.ASSISTANT_NAME}. Produce a short "Good morning" daily brief.
Current date and time: {time_info}. When you say "today" use: {today_phrase}.
Address the user as {user_label}. Be concise, natural, and slightly professional.
Rules:
- Weather: Only if a "Weather" block is provided below, include that weather in the brief. If there is NO Weather block, do not write any sentence about weather—do not say "I don't have weather", "check a reliable source", or similar. Omit weather entirely.
- Include only the sections that are provided below (e.g. Upcoming reminders, What happened today)."""
    parts = []
    if weather:
        parts.append("Weather (use this in your brief):\n" + weather)
    else:
        parts.append("Weather: NOT PROVIDED. Do not include any Weather section or sentence in your brief. Do not suggest checking external sources.")
    if headlines:
        parts.append("Headlines / recent context:\n" + (headlines[:2000] if len(headlines) > 2000 else headlines))
    if upcoming_lines:
        parts.append("Upcoming reminders (mention only these in the brief):\n" + "\n".join(upcoming_lines))
    if previous_lines:
        parts.append("What happened today (reminders that already went off today; list in a short 'What happened today' section):\n" + "\n".join(previous_lines))
    if learning:
        parts.append("Stored knowledge (for context only, do not list):\n" + learning[:1200])
    if not parts:
        parts.append("No external data. Still give a brief greeting and mention the date/time.")
    user_prompt = "\n\n---\n\n".join(parts) + "\n\nWrite the brief now. If 'What happened today' is provided, include a short sentence or two for it. Keep total length to a few sentences."

    try:
        llm = GroqService.get_llm()
        from langchain_core.messages import SystemMessage, HumanMessage
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user_prompt)])
        text = resp.content if hasattr(resp, "content") else str(resp)
        return (text or "Good morning. Have a great day.").strip()
    except Exception as e:
        logger.warning("Brief LLM failed: %s", e)
        fallback = f"Good morning. It's {today_phrase}."
        if weather:
            fallback += " " + weather.split("\n")[0]
        return fallback


def generate_brief_for_user(
    user_id: int,
    user_name: Optional[str] = None,
    city: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """
    Generate today's brief text and optional WAV path for user.
    Returns (text, audio_path). audio_path is None if Murf not configured or TTS failed.
    """
    brief_date = date.today().isoformat()
    text = generate_brief_text(user_id=user_id, user_name=user_name, city=city)
    audio_path = None
    if config.MURF_API_KEY:
        briefs_dir = get_settings().base_dir / "database" / "briefs" / str(user_id)
        briefs_dir.mkdir(parents=True, exist_ok=True)
        wav_path = briefs_dir / f"{brief_date}.wav"
        if text_to_speech_wav(text, wav_path):
            audio_path = str(wav_path)
    return text, audio_path


def run_scheduled_brief_for_default_user() -> None:
    """Generate and store today's brief for the default admin user (for scheduler)."""
    from app.db import get_user_by_email, upsert_daily_brief, db_available
    if not db_available:
        return
    settings = get_settings()
    admin = get_user_by_email(settings.DEFAULT_ADMIN_EMAIL)
    if not admin:
        return
    user_id = admin["id"]
    user_name = (admin.get("name") or "").strip() or None
    try:
        text, audio_path = generate_brief_for_user(user_id, user_name=user_name)
        brief_date = date.today().isoformat()
        upsert_daily_brief(user_id, brief_date, text, audio_path=audio_path)
        logger.info("Scheduled daily brief generated for user_id=%s", user_id)
    except Exception as e:
        logger.warning("Scheduled brief failed: %s", e)
