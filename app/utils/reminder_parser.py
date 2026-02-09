"""
Parse natural-language reminder requests from chat (e.g. "remind me in 30 minutes to call Mom").
Returns (in_minutes, message) or None if not a reminder request.
"""
import re
from typing import Optional, Tuple

# Patterns: "remind me in N minutes/hours to X" or "set a reminder for N hours: X"
_RE_MINUTES = re.compile(
    r"(?:remind\s+me|set\s+(?:a\s+)?reminder)(?:\s+for)?\s+in\s+(\d+)\s+(?:minute|minutes|min|mins)s?\s+(?:to|:)\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)
_RE_HOURS = re.compile(
    r"(?:remind\s+me|set\s+(?:a\s+)?reminder)(?:\s+for)?\s+in\s+(\d+)\s+(?:hour|hours|hr|hrs)s?\s+(?:to|:)\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)
# "in 30 minutes remind me to X" variant
_RE_MINUTES_ALT = re.compile(
    r"in\s+(\d+)\s+(?:minute|minutes|min|mins)s?\s+(?:remind\s+me\s+to|to\s+remind\s+me)\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)
_RE_HOURS_ALT = re.compile(
    r"in\s+(\d+)\s+(?:hour|hours|hr|hrs)s?\s+(?:remind\s+me\s+to|to\s+remind\s+me)\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)

MAX_MESSAGE_LEN = 2000
MAX_MINUTES = 43200  # 30 days


def parse_reminder_intent(text: str) -> Optional[Tuple[int, str]]:
    """
    If text looks like a reminder request, return (in_minutes, message).
    Otherwise return None.
    """
    if not text or not text.strip():
        return None
    text = text.strip()

    for pattern, is_hours in [
        (_RE_MINUTES, False),
        (_RE_HOURS, True),
        (_RE_MINUTES_ALT, False),
        (_RE_HOURS_ALT, True),
    ]:
        m = pattern.search(text)
        if m:
            num = int(m.group(1))
            rest = (m.group(2) or "").strip()
            if not rest:
                rest = "Reminder"
            if is_hours:
                in_minutes = num * 60
            else:
                in_minutes = num
            if in_minutes < 1:
                in_minutes = 1
            if in_minutes > MAX_MINUTES:
                in_minutes = MAX_MINUTES
            message = rest[:MAX_MESSAGE_LEN]
            return (in_minutes, message)
    return None
