"""
Lightweight state for admin/ops: last Groq key used, rebuild time, vector store stats.
"""
import time
import json
from pathlib import Path
from typing import Optional

import config

# In-memory state (reset on restart)
_last_groq_key_masked: Optional[str] = None
_last_groq_used_at: Optional[float] = None

# Stats file for vector store (persists across restarts)
STATS_FILE = config.VECTOR_STORE_DIR / "ops_stats.json"


def set_groq_key_used(key: str) -> None:
    """Record that a Groq API key was used (store masked suffix only)."""
    global _last_groq_key_masked, _last_groq_used_at
    _last_groq_key_masked = key[-4:] if key and len(key) >= 4 else "****"
    _last_groq_used_at = time.time()


def get_groq_key_status() -> dict:
    """Return last-used key (masked) and timestamp."""
    return {
        "last_used_key_suffix": _last_groq_key_masked,
        "last_used_at": _last_groq_used_at,
        "keys_in_rotation": len(config.GROQ_API_KEYS),
    }


def set_vector_store_stats(doc_count: int, last_rebuild: Optional[float] = None) -> None:
    """Update vector store stats (call from VectorStore.build / add_memory)."""
    data = _read_stats()
    data["vector_store_doc_count"] = doc_count
    if last_rebuild is not None:
        data["last_rebuild_time"] = last_rebuild
    _write_stats(data)


def _read_stats() -> dict:
    if not STATS_FILE.exists():
        return {"vector_store_doc_count": 0, "last_rebuild_time": None}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"vector_store_doc_count": 0, "last_rebuild_time": None}


def _write_stats(data: dict) -> None:
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_vector_store_status() -> dict:
    """Return vector store doc count and last rebuild time from stats file."""
    data = _read_stats()
    return {
        "doc_count": data.get("vector_store_doc_count", 0),
        "last_rebuild_time": data.get("last_rebuild_time"),
        "index_path": str(config.VECTOR_STORE_DIR),
    }
