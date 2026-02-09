"""
Parse request log file and aggregate usage for admin dashboard.
Reads from config LOG_FILE (same as main app structured JSON logs).
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import get_settings


def _log_path() -> Path:
    p = Path(get_settings().log_file)
    if not p.is_absolute():
        p = get_settings().base_dir / p
    return p


def parse_log_lines(max_lines: int = 5000):
    """Read log file and yield parsed JSON objects (newest first)."""
    path = _log_path()
    if not path.exists():
        return
    lines: List[dict] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    lines.append(data)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return
    for obj in reversed(lines[-max_lines:]):
        yield obj


def _latency_bucket(ms: Optional[float]) -> Optional[str]:
    if ms is None:
        return None
    ms = float(ms)
    if ms < 1000:
        return "0-1s"
    if ms < 3000:
        return "1-3s"
    if ms < 5000:
        return "3-5s"
    if ms < 10000:
        return "5-10s"
    return "10s+"


def aggregate_usage(hours: int = 24) -> Dict[str, Any]:
    """Aggregate requests by hour, mode, status, latency. Returns stats for dashboard."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    by_hour: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "general": 0, "realtime": 0, "success": 0, "errors": 0}
    )
    by_mode: Dict[str, int] = {"general": 0, "realtime": 0}
    by_status: Dict[str, int] = defaultdict(int)
    latency_buckets: Dict[str, int] = defaultdict(int)
    latencies: List[float] = []
    total_requests = 0
    error_count = 0
    success_count = 0

    for obj in parse_log_lines():
        path = obj.get("path", "")
        if "/chat/general" not in path and "/chat/realtime" not in path:
            continue
        total_requests += 1
        mode = obj.get("mode") or ("general" if "general" in path else "realtime")
        by_mode[mode] = by_mode.get(mode, 0) + 1
        status = obj.get("status_code", 0)
        by_status[str(status)] += 1
        if status >= 400:
            error_count += 1
        else:
            success_count += 1
        lat = obj.get("latency_ms")
        if lat is not None:
            latencies.append(float(lat))
            bucket = _latency_bucket(lat)
            if bucket:
                latency_buckets[bucket] += 1
        ts = obj.get("timestamp")
        if ts is not None:
            try:
                dt = datetime.utcfromtimestamp(ts)
                if dt >= cutoff:
                    key = dt.strftime("%Y-%m-%d %H:00")
                    by_hour[key]["total"] += 1
                    if mode == "general":
                        by_hour[key]["general"] += 1
                    else:
                        by_hour[key]["realtime"] += 1
                    if status >= 400:
                        by_hour[key]["errors"] += 1
                    else:
                        by_hour[key]["success"] += 1
            except (TypeError, ValueError):
                pass

    sorted_hours = sorted(by_hour.items())
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    bucket_order = ["0-1s", "1-3s", "3-5s", "5-10s", "10s+"]
    sorted_buckets = [(b, latency_buckets[b]) for b in bucket_order if latency_buckets[b]]

    return {
        "total_requests": total_requests,
        "success_count": success_count,
        "error_count": error_count,
        "by_mode": dict(by_mode),
        "by_status": dict(by_status),
        "by_hour": dict(sorted_hours),
        "sorted_hours": sorted_hours,
        "sorted_latency_buckets": sorted_buckets,
        "avg_latency_ms": round(avg_latency, 2),
        "latency_samples": len(latencies),
    }


def recent_requests(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Last N requests for the table (newest first). Supports offset for pagination."""
    rows: List[Dict[str, Any]] = []
    skipped = 0
    for obj in parse_log_lines(max_lines=2000):
        path = obj.get("path", "")
        if "/chat/" not in path:
            continue
        if offset and skipped < offset:
            skipped += 1
            continue
        mode = obj.get("mode") or ("general" if "general" in path else "realtime")
        sid = obj.get("session_id")
        session_display = (sid[:8] + "...") if sid else "-"
        ts = obj.get("timestamp")
        ts_str = ""
        if ts is not None:
            try:
                ts_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC")
            except (TypeError, ValueError):
                ts_str = str(ts)
        rows.append({
            "path": path,
            "method": obj.get("method", ""),
            "client_ip": obj.get("client_ip", ""),
            "status_code": obj.get("status_code"),
            "latency_ms": obj.get("latency_ms"),
            "mode": mode,
            "session_id": session_display,
            "timestamp": ts_str,
        })
        if len(rows) >= limit:
            break
    return rows


def log_file_available() -> bool:
    """Return True if the log file exists and is readable."""
    return _log_path().exists()
