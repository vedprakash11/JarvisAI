"""
Detect if a user query needs recent/current data (use Tavily) or can be answered from general knowledge (LLM only).
Used to minimize cost: skip Tavily for general queries like "What is machine learning?".
"""
import re
from datetime import datetime

# Phrases that suggest the user wants up-to-date / recent information → use Tavily
NEEDS_RECENT_PATTERN = re.compile(
    r"\b("
    r"latest|recent|current|new\s+news|news\s+(?:today|now)?|"
    r"today'?s?|this\s+(?:week|month|year|morning|afternoon|evening)|tonight|"
    r"right\s+now|just\s+(?:now|happened)|breaking|headline|"
    r"what'?s\s+happening|what\s+happened\s+(?:today|recently)|"
    r"current\s+events?|live\s+(?:score|update|news)|"
    r"(\d{4})\s*(?:election|news|update)|"  # e.g. "2025 election"
    r"stock\s+price|share\s+price|crypto\s+price|bitcoin\s+price|"
    r"who\s+won|who\s+is\s+leading|score\s+(?:of|for)|"
    r"election\s+result|match\s+result|game\s+result"
    r")\b",
    re.IGNORECASE,
)

# Year in query (e.g. "AI news 2025") can suggest recency
_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def needs_recent_data(message: str) -> bool:
    """
    Return True if the query likely needs fresh/recent data (use Tavily).
    Return False for general-knowledge queries (answer with LLM only to save cost).
    """
    if not (message or "").strip():
        return False
    msg = message.strip()
    if NEEDS_RECENT_PATTERN.search(msg):
        return True
    # Explicit recent year (e.g. "AI developments 2024") suggests recency
    current_year = datetime.now().year
    years = _YEAR_PATTERN.findall(msg)
    if years and any(int(y) >= current_year - 1 for y in years):
        return True
    return False
