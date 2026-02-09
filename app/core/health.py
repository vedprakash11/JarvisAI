"""Health checks: liveness (process up) and readiness (dependencies reachable)."""
from typing import Any, Dict

from app.db import db_available, get_connection


def check_live() -> Dict[str, Any]:
    """Liveness: app process is running."""
    return {"status": "ok", "check": "live"}


def check_ready() -> Dict[str, Any]:
    """Readiness: DB (and optionally other deps) are reachable."""
    db_ok = False
    if db_available:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            db_ok = True
        except Exception:
            pass
    return {
        "status": "ok" if db_ok else "degraded",
        "check": "ready",
        "database": "up" if db_ok else "down",
    }
