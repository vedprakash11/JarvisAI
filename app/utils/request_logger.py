"""
Structured request logging: path, method, client_ip, session_id, mode, status_code, latency_ms.
"""
import json
import logging
import time
from pathlib import Path

import config


def _log_path() -> Path:
    p = Path(config.LOG_FILE)
    if not p.is_absolute():
        p = config.BASE_DIR / p
    return p


def setup_request_logger() -> logging.Logger:
    """Configure and return a logger for request logs."""
    log_path = _log_path()
    logger = logging.getLogger("jarvisai.requests")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        if log_path and str(log_path).strip():
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(log_path, encoding="utf-8")
        else:
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


REQUEST_LOGGER = setup_request_logger()


def log_request(request, status_code: int, latency_ms: float) -> None:
    """Emit one structured JSON log line (request_id, user context, tool, query when available)."""
    try:
        state = getattr(request, "state", None)
        session_id = getattr(state, "session_id", None) if state else None
        mode = getattr(state, "mode", None) if state else None
        tool = getattr(state, "tool", None) if state else None
        query = getattr(state, "query", None) if state else None
        request_id = getattr(state, "request_id", None) if state else None
        client_ip = request.client.host if request.client else ""
        payload = {
            "path": request.url.path,
            "method": request.method,
            "client_ip": client_ip,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 2),
            "timestamp": time.time(),
        }
        if request_id:
            payload["request_id"] = request_id
        if session_id:
            payload["session_id"] = session_id
        if mode:
            payload["mode"] = mode
        if tool:
            payload["tool"] = tool
        if query:
            payload["query"] = query
        REQUEST_LOGGER.info(json.dumps(payload))
    except Exception:
        pass
