"""
Background worker: poll for due reminders, create dashboard notifications (with optional Murf TTS),
and optional webhook. Run from app lifespan as a daemon thread.
"""
import logging
import threading
from pathlib import Path

import config
from app.db import (
    get_due_reminders,
    mark_reminder_sent,
    mark_reminder_failed,
    create_notification,
    update_notification_audio,
)
from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None


def _send_webhook(reminder: dict) -> bool:
    """POST reminder to REMINDER_WEBHOOK_URL. Returns True if sent or no URL."""
    url = (config.REMINDER_WEBHOOK_URL or "").strip()
    if not url:
        return True
    try:
        import urllib.request
        import json
        body = json.dumps({
            "reminder_id": reminder.get("id"),
            "user_id": reminder.get("user_id"),
            "message": reminder.get("message"),
            "run_at": reminder.get("run_at").isoformat() if hasattr(reminder.get("run_at"), "isoformat") else str(reminder.get("run_at")),
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        logger.warning("Reminder webhook failed: %s", e)
        return False


def _generate_reminder_voice(notification_id: int, message: str) -> None:
    """Generate Murf TTS for reminder and save to file; update notification with audio_path."""
    if not config.MURF_API_KEY:
        return
    try:
        from app.utils.murf_tts import text_to_speech_wav
        text = f"You have a reminder. {message}" if message else "You have a reminder."
        base_dir = get_settings().base_dir
        audio_dir = base_dir / "database" / "reminder_audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        wav_path = audio_dir / f"{notification_id}.wav"
        if text_to_speech_wav(text, wav_path):
            update_notification_audio(notification_id, str(wav_path))
            logger.info("Reminder voice generated for notification %s", notification_id)
    except Exception as e:
        logger.warning("Reminder TTS failed: %s", e)


def _process_due_reminders():
    """Fetch due reminders, create notifications (with optional voice), optional webhook, mark sent/failed."""
    try:
        from app.db import db_available
        if not db_available:
            return
    except Exception:
        return
    due = get_due_reminders()
    for r in due:
        rid = r.get("id")
        user_id = r.get("user_id")
        message = (r.get("message") or "").strip()
        try:
            nid = create_notification(user_id=user_id, title="Reminder", body=message, source="reminder")
            _generate_reminder_voice(nid, message)
            if config.REMINDER_WEBHOOK_URL:
                _send_webhook(r)
            mark_reminder_sent(rid)
            logger.info("Reminder %s sent for user %s", rid, user_id)
        except Exception as e:
            logger.warning("Reminder %s failed: %s", rid, e)
            mark_reminder_failed(rid)


def _run_loop():
    interval = max(30, getattr(config, "REMINDER_CHECK_INTERVAL_SECONDS", 60))
    while not _stop.is_set():
        try:
            _process_due_reminders()
        except Exception as e:
            logger.warning("Reminder worker iteration failed: %s", e)
        _stop.wait(timeout=interval)


def start_reminder_worker():
    """Start the reminder worker in a daemon thread."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run_loop, daemon=True)
    _thread.start()
    logger.info("Reminder worker started (interval=%ss)", getattr(config, "REMINDER_CHECK_INTERVAL_SECONDS", 60))


def stop_reminder_worker():
    """Signal the worker to stop (e.g. on shutdown)."""
    _stop.set()
