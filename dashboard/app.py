"""
Flask admin dashboard: usage stats from logs + status from JarvisAI API.
Login is against the MySQL admins table (no .env credentials). API status uses JWT if the same admin exists in the API's users table.
"""
from datetime import datetime
import requests
from flask import Flask, redirect, render_template, request, session, url_for
from passlib.context import CryptContext

from dashboard.config import JARVIS_API_URL, SECRET_KEY
from dashboard.db import get_admin_by_email
from dashboard.usage import aggregate_usage, recent_requests

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@app.context_processor
def inject_common():
    return {"api_url": JARVIS_API_URL, "current_user_email": session.get("email")}


def _verify_admin_login(email: str, password: str) -> bool:
    """Verify credentials against the admins table. Returns True if valid."""
    admin = get_admin_by_email(email)
    if not admin or not admin.get("password_hash"):
        return False
    return pwd_ctx.verify(password, admin["password_hash"])


def _api_login(email, password):
    """Return (token, None) on success, or (None, error_message). Used to get JWT for /admin/status."""
    try:
        r = requests.post(
            f"{JARVIS_API_URL.rstrip('/')}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not r.ok:
            detail = data.get("detail", data.get("message", "Login failed"))
            if isinstance(detail, list) and detail:
                detail = detail[0].get("msg", str(detail[0]))
            return None, detail if isinstance(detail, str) else "Login failed"
        token = data.get("access_token")
        if not token:
            return None, "No token in response"
        return token, None
    except requests.RequestException:
        return None, "Cannot reach API. Is the JarvisAI API running?"
    except Exception as e:
        return None, str(e) or "Login failed"


def fetch_api_status(token):
    """GET /admin/status using the given Bearer token. Returns (data, error) with error in (None, 'unauthorized', 'unreachable')."""
    base = JARVIS_API_URL.rstrip("/")
    if not token:
        return None, "unauthorized"

    try:
        r = requests.get(
            f"{base}/admin/status",
            timeout=5,
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.ok:
            data = r.json()
            vs = data.get("vector_store") or {}
            ts = vs.get("last_rebuild_time")
            if ts is not None:
                try:
                    vs = {**vs, "last_rebuild_str": datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")}
                except (TypeError, ValueError):
                    vs = {**vs, "last_rebuild_str": str(ts)}
            else:
                vs = {**vs, "last_rebuild_str": "—"}
            data["vector_store"] = vs
            return data, None
        if r.status_code == 401:
            return None, "unauthorized"
    except Exception:
        pass
    return None, "unreachable"


def fetch_notifications(token):
    """GET /notifications. Returns list of notifications or [] on error."""
    base = JARVIS_API_URL.rstrip("/")
    if not token:
        return []
    try:
        r = requests.get(f"{base}/notifications", timeout=5, headers={"Authorization": f"Bearer {token}"}, params={"limit": 30})
        if r.ok:
            data = r.json()
            return data.get("items") or []
    except Exception:
        pass
    return []


def fetch_brief(token):
    """GET /brief. Returns dict with text, audio_url, brief_date or None."""
    base = JARVIS_API_URL.rstrip("/")
    if not token:
        return None
    try:
        r = requests.get(f"{base}/brief", timeout=15, headers={"Authorization": f"Bearer {token}"})
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("email"):
            return redirect(url_for("index"))
        return render_template("login.html", error=None)

    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    if not email or not password:
        return render_template("login.html", error="Email and password required")

    if not _verify_admin_login(email, password):
        return render_template("login.html", error="Invalid email or password")

    session["email"] = email
    token, _ = _api_login(email, password)
    if token:
        session["token"] = token
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("token", None)
    session.pop("email", None)
    return redirect(url_for("login"))


def login_required(f):
    def wrapped(*args, **kwargs):
        if not session.get("email"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    wrapped.__name__ = f.__name__
    return wrapped


def _overview_insights(usage):
    """Compute overview KPIs and insight strings from usage dict."""
    usage = usage or {}
    total = usage.get("total_requests") or 0
    success = usage.get("success_count") or 0
    errors = usage.get("error_count") or 0
    success_rate = round((success / total) * 100) if total else 0
    error_rate = round((errors / total) * 100) if total else 0
    by_mode = usage.get("by_mode") or {}
    general = by_mode.get("general", 0)
    realtime = by_mode.get("realtime", 0)
    mode_total = general + realtime
    general_pct = round((general / mode_total) * 100) if mode_total else 0
    realtime_pct = round((realtime / mode_total) * 100) if mode_total else 0

    peak_label, peak_count = "", 0
    for label, data in usage.get("sorted_hours") or []:
        tot = (data or {}).get("total", 0)
        if tot > peak_count:
            peak_count = tot
            peak_label = label

    by_status = usage.get("by_status") or {}
    status_2xx = sum(v for k, v in by_status.items() if str(k).startswith("2"))
    status_4xx = sum(v for k, v in by_status.items() if str(k).startswith("4"))
    status_5xx = sum(v for k, v in by_status.items() if str(k).startswith("5"))

    if total == 0:
        health_summary = "No traffic in the last 24h. Usage will appear once requests are logged."
    elif errors == 0:
        health_summary = "All requests succeeded in the last 24h."
    else:
        health_summary = "Some errors in the last 24h. Check the Activity tab for details."

    return {
        "success_rate_pct": success_rate,
        "error_rate_pct": error_rate,
        "peak_hour_label": peak_label,
        "peak_hour_count": peak_count,
        "health_summary": health_summary,
        "status_2xx": status_2xx,
        "status_4xx": status_4xx,
        "status_5xx": status_5xx,
        "general_pct": general_pct,
        "realtime_pct": realtime_pct,
    }


@app.route("/api/notifications/audio/<int:nid>")
@login_required
def notification_audio_proxy(nid):
    """Proxy to JarvisAI API /notifications/audio/<id> so browser can play reminder voice with same-origin request."""
    token = session.get("token")
    if not token:
        return "Unauthorized", 401
    base = JARVIS_API_URL.rstrip("/")
    try:
        r = requests.get(
            f"{base}/notifications/audio/{nid}",
            timeout=30,
            headers={"Authorization": f"Bearer {token}"},
            stream=True,
        )
        if not r.ok:
            return r.text or "Error", r.status_code
        from flask import Response
        return Response(
            r.iter_content(chunk_size=8192),
            status=200,
            mimetype=r.headers.get("Content-Type", "audio/wav"),
            headers={"Content-Disposition": "inline"},
        )
    except requests.RequestException:
        return "Service unavailable", 503


@app.route("/api/brief/audio")
@login_required
def brief_audio_proxy():
    """Proxy to JarvisAI API /brief/audio so browser can play with same-origin request (token in session)."""
    date_param = request.args.get("date")
    token = session.get("token")
    if not token:
        return "Unauthorized", 401
    base = JARVIS_API_URL.rstrip("/")
    try:
        r = requests.get(
            f"{base}/brief/audio",
            timeout=30,
            headers={"Authorization": f"Bearer {token}"},
            params={"date": date_param} if date_param else {},
            stream=True,
        )
        if not r.ok:
            return r.text or "Error", r.status_code
        from flask import Response
        return Response(
            r.iter_content(chunk_size=8192),
            status=200,
            mimetype=r.headers.get("Content-Type", "audio/wav"),
            headers={"Content-Disposition": "inline"},
        )
    except requests.RequestException:
        return "Service unavailable", 503


@app.route("/")
@login_required
def index():
    token = session.get("token")
    status, status_error = fetch_api_status(token)
    if status_error == "unauthorized":
        session.pop("token", None)

    notifications = fetch_notifications(token) if token else []
    brief = fetch_brief(token) if token else None

    usage = aggregate_usage(hours=24)
    recent = recent_requests(limit=50)
    insights = _overview_insights(usage)
    return render_template(
        "index.html",
        usage=usage,
        status=status,
        status_error=status_error,
        recent=recent,
        insights=insights,
        notifications=notifications,
        brief=brief,
    )
