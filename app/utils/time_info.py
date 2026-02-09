"""
Current date and time utilities for LLM context.
"""
from datetime import datetime


def get_current_datetime_str() -> str:
    """Return current date and time as a string for prompts."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_current_date_str() -> str:
    """Return current date only."""
    return datetime.now().strftime("%Y-%m-%d")


def get_current_time_str() -> str:
    """Return current time only."""
    return datetime.now().strftime("%H:%M:%S")


def get_current_date_natural() -> str:
    """Return current date in a natural form for search and answers (e.g. '8 February 2025')."""
    d = datetime.now()
    return f"{d.day} {d.strftime('%B')} {d.year}"


def get_today_phrase() -> str:
    """Return a short phrase for 'today' in answers (e.g. 'Today, 8 February 2025')."""
    d = datetime.now()
    return f"Today, {d.day} {d.strftime('%B')} {d.year}"
