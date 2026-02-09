"""
FastAPI application and API endpoints.
Layered: API -> service -> repository. DI for repositories and shared ChatService.
"""
import logging
import time
import uuid

logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Optional

from fastapi import FastAPI, HTTPException, Request, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import config
from app.core.settings import get_settings
from app.core.health import check_live, check_ready
from app.models import (
    ChatRequest,
    ChatResponse,
    RegisterRequest,
    TokenResponse,
    UserInfo,
    SessionSummary,
    SessionListResponse,
    SessionHistoryResponse,
    ErrorResponse,
    ErrorDetail,
    AdminUsageResponse,
    AdminRequestRow,
    AdminRequestsResponse,
    AdminDashboardConfigResponse,
)
from app.utils import log_usage
from app.services.chat_service import ChatService
from app.utils import ops_state
from app.utils.request_logger import log_request
from app.auth import (
    get_current_user,
    get_current_admin_user,
    hash_password,
    verify_password,
    create_access_token,
)
from app.db import (
    init_db,
    db_available,
    seed_default_admin,
    get_user_by_email,
    create_user,
    update_user_password,
)
from app.repositories import FileChatSessionRepository
from app.deps import get_user_repository
from app.repositories.protocols import UserRepository
from app.core.settings import get_settings
from app.db import (
    create_reminder,
    get_reminders_for_user,
    get_daily_brief,
    upsert_daily_brief,
    get_notifications_for_user,
)
from app.services.brief_service import generate_brief_for_user, run_scheduled_brief_for_default_user
from app.utils.reminder_worker import start_reminder_worker, stop_reminder_worker
from app.utils.reminder_parser import parse_reminder_intent
from app.models import (
    ReminderCreate,
    ReminderItem,
    ReminderListResponse,
    BriefResponse,
    NotificationItem,
    NotificationListResponse,
)

def _start_brief_scheduler():
    """Start APScheduler for daily brief at configured hour."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        hour = get_settings().brief_hour
        scheduler = BackgroundScheduler()
        scheduler.add_job(run_scheduled_brief_for_default_user, "cron", hour=hour, minute=0)
        scheduler.start()
        logger.info("Daily brief scheduler started (hour=%s)", hour)
    except Exception as e:
        logger.warning("Brief scheduler failed to start: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, seed default admin, create shared ChatService, load/build vector store, start reminder worker and brief scheduler."""
    init_db()
    if db_available:
        settings = get_settings()
        admin_email = (settings.default_admin_email or "").strip()
        admin_password = (settings.default_admin_password or "").strip()
        if admin_email and admin_password:
            admin_hash = hash_password(admin_password)
            seed_default_admin(admin_email, admin_hash)
            existing = get_user_by_email(admin_email)
            if existing is None:
                try:
                    create_user(admin_email, admin_hash, "Admin")
                except Exception:
                    pass
            else:
                update_user_password(admin_email, admin_hash)
    chat_repo = FileChatSessionRepository()
    chat_svc = ChatService(chat_repo)
    chat_svc.vector_store.load() or chat_svc.vector_store.build()
    app.state.chat_service = chat_svc
    start_reminder_worker()
    _start_brief_scheduler()
    yield
    stop_reminder_worker()


def get_chat_service(request: Request) -> ChatService:
    """Dependency: shared ChatService from app.state (set in lifespan)."""
    return request.app.state.chat_service


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="JarvisAI",
    description="Chat API with user auth and per-user chat storage",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalize_detail(detail: object) -> list:
    """Convert FastAPI/HTTPException detail to list of strings for ErrorResponse."""
    if isinstance(detail, str):
        return [detail]
    if isinstance(detail, list):
        out = []
        for d in detail:
            if isinstance(d, str):
                out.append(d)
            elif isinstance(d, dict):
                out.append(d.get("msg", d.get("message", str(d))))
            else:
                out.append(str(d))
        return out if out else ["Error"]
    return [str(detail)]


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return structured ErrorResponse for 4xx/5xx. Includes request_id when available."""
    details = _normalize_detail(exc.detail)
    body = ErrorResponse(
        code=str(exc.status_code),
        message=details[0] if details else "Error",
        details=[ErrorDetail(code=str(exc.status_code), message=d) for d in details],
    )
    payload = body.model_dump()
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        payload["request_id"] = request_id
    response = JSONResponse(status_code=exc.status_code, content=payload)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Set request_id on request.state and add X-Request-ID to response."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security-related headers to responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = (time.perf_counter() - start) * 1000
    log_request(request, response.status_code, latency_ms)
    return response


# ----- Auth (no auth required) -----

@app.post("/auth/register", response_model=TokenResponse)
def register(
    body: RegisterRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
):
    """Register a new user. Returns JWT and user info."""
    if not db_available:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Set MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE in .env and ensure MySQL is running.",
        )
    email = body.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    existing = user_repo.get_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    try:
        user_id = user_repo.create(email, hash_password(body.password), body.name or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TokenResponse(
        access_token=create_access_token(str(user_id)),
        user=UserInfo(id=user_id, email=email, name=(body.name or "").strip()),
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(
    body: RegisterRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
):
    """Login with email and password. Returns JWT and user info."""
    if not db_available:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Set MYSQL_* in .env and ensure MySQL is running.",
        )
    email = body.email.strip().lower()
    user = user_repo.get_by_email(email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(
        access_token=create_access_token(str(user["id"])),
        user=UserInfo(id=user["id"], email=user["email"], name=user.get("name") or ""),
    )


@app.get("/me", response_model=UserInfo)
def me(current_user: dict = Depends(get_current_user)):
    """Return current user (requires Bearer token). Includes is_admin when email is in ADMIN_EMAILS."""
    return UserInfo(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user.get("name") or "",
        is_admin=current_user.get("is_admin", False),
    )


# ----- Chat (auth required, per-user) -----

@app.get("/chats/sessions", response_model=SessionListResponse)
def list_sessions(
    request: Request,
    current_user: dict = Depends(get_current_user),
    chat_svc: Annotated[ChatService, Depends(get_chat_service)] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List current user's chat sessions (newest first). Paginated: limit (1-100), offset."""
    if limit < 1 or limit > 100:
        limit = 50
    if offset < 0:
        offset = 0
    items, total = chat_svc.list_sessions(current_user["id"], limit=limit, offset=offset)
    return SessionListResponse(items=[SessionSummary(**s) for s in items], total=total)


@app.get("/chats/sessions/{session_id}", response_model=SessionHistoryResponse)
def get_session_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    chat_svc: Annotated[ChatService, Depends(get_chat_service)] = None,
):
    """Get message history for a session (user-scoped)."""
    history = chat_svc.get_history(current_user["id"], session_id)
    return SessionHistoryResponse(session_id=session_id, messages=history)


def _try_create_reminder_from_chat(user_id: int, message: str, chat_svc: ChatService, session_id: str) -> Optional[str]:
    """If message is a reminder request, create reminder in DB and return confirmation reply. Else return None."""
    parsed = parse_reminder_intent(message)
    if not parsed:
        return None
    in_minutes, reminder_message = parsed
    if not db_available:
        return None
    from datetime import datetime, timedelta
    run_at = datetime.utcnow() + timedelta(minutes=in_minutes)
    try:
        create_reminder(user_id, reminder_message, run_at)
    except Exception:
        return None
    # Persist user message and our reply in chat history
    chat_svc.append_message(user_id, session_id, "user", message)
    if in_minutes >= 60:
        time_desc = f"{in_minutes // 60} hour{'s' if in_minutes != 60 else ''} from now"
    else:
        time_desc = f"{in_minutes} minute{'s' if in_minutes != 1 else ''} from now"
    reply = f"Done. I've set a reminder for {time_desc}: {reminder_message}. You'll see it in the dashboard Alerts when it's time."
    chat_svc.append_message(user_id, session_id, "assistant", reply)
    return reply


@app.post("/chat/general", response_model=ChatResponse)
@limiter.limit(config.RATE_LIMIT_CHAT)
def chat_general(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
    chat_svc: Annotated[ChatService, Depends(get_chat_service)] = None,
):
    try:
        session_id = chat_svc.get_or_create_session_id(current_user["id"], body.session_id)
        request.state.session_id = session_id
        request.state.mode = "general"
        request.state.query = (body.message or "")[:200]

        reminder_reply = _try_create_reminder_from_chat(current_user["id"], body.message, chat_svc, session_id)
        if reminder_reply is not None:
            request.state.tool = "reminder"
            return ChatResponse(reply=reminder_reply, session_id=session_id)

        request.state.tool = "llm answer"
        reply = chat_svc.chat_general(current_user["id"], session_id, body.message)
        return ChatResponse(reply=reply, session_id=session_id)
    except ValueError as e:
        logger.exception("chat_general ValueError")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("chat_general failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/realtime", response_model=ChatResponse)
@limiter.limit(config.RATE_LIMIT_CHAT)
def chat_realtime(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
    chat_svc: Annotated[ChatService, Depends(get_chat_service)] = None,
):
    try:
        session_id = chat_svc.get_or_create_session_id(current_user["id"], body.session_id)
        request.state.session_id = session_id
        request.state.mode = "realtime"
        request.state.query = (body.message or "")[:200]

        reminder_reply = _try_create_reminder_from_chat(current_user["id"], body.message, chat_svc, session_id)
        if reminder_reply is not None:
            request.state.tool = "reminder"
            return ChatResponse(reply=reminder_reply, session_id=session_id)

        reply, tool_used = chat_svc.chat_realtime(
            current_user["id"],
            session_id,
            body.message,
            search_query=body.search_query,
        )
        request.state.tool = tool_used
        return ChatResponse(reply=reply, session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rebuild")
def rebuild(
    current_user: dict = Depends(get_current_user),
    chat_svc: Annotated[ChatService, Depends(get_chat_service)] = None,
):
    """Rebuild vector store (auth required)."""
    try:
        chat_svc.rebuild_vector_store()
        return {"status": "ok", "message": "Vector store rebuilt."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- Voice (offline STT with Whisper tiny; no OpenAI API key) -----


WAKE_PHRASE = "hey jarvis"


@app.post("/voice/transcribe")
async def voice_transcribe(
    current_user: dict = Depends(get_current_user),
    audio: Annotated[UploadFile, File(description="Audio file (webm/wav)")] = None,
):
    """Transcribe audio to text using local Whisper tiny. Returns { text, language, woke }."""
    if not audio:
        raise HTTPException(status_code=400, detail="Missing audio file.")
    data = await audio.read()
    content_type = audio.content_type or ""
    try:
        from app.utils.whisper_stt import transcribe_audio
        text, lang = transcribe_audio(bytes(data), content_type)
    except Exception as e:
        logger.exception("Voice transcribe failed: %s", e)
        raise HTTPException(status_code=500, detail="Transcription failed.")
    text_lower = (text or "").strip().lower()
    woke = WAKE_PHRASE in text_lower
    return {"text": text or "", "language": lang, "woke": woke}


# ----- Reminders (any authenticated user; all data scoped by current_user["id"]) -----


@app.post("/reminders", response_model=ReminderItem)
def create_reminder_endpoint(
    body: ReminderCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a reminder. Use in_minutes (e.g. 30) or run_at (ISO datetime)."""
    if not db_available:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    from datetime import datetime, timedelta
    if body.in_minutes is not None:
        run_at = datetime.utcnow() + timedelta(minutes=body.in_minutes)
    elif body.run_at:
        try:
            run_at = datetime.fromisoformat(body.run_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="run_at must be ISO 8601 datetime.")
    else:
        raise HTTPException(status_code=400, detail="Provide in_minutes or run_at.")
    rid = create_reminder(current_user["id"], body.message, run_at)
    return ReminderItem(
        id=rid,
        user_id=current_user["id"],
        message=body.message,
        run_at=run_at,
        status="pending",
        created_at=datetime.utcnow(),
    )


@app.get("/reminders", response_model=ReminderListResponse)
def list_reminders(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """List current user's reminders (all statuses)."""
    if limit < 1 or limit > 100:
        limit = 50
    if offset < 0:
        offset = 0
    items, total = get_reminders_for_user(current_user["id"], limit=limit, offset=offset)
    return ReminderListResponse(
        items=[ReminderItem(**r) for r in items],
        total=total,
    )


# ----- Notifications (per-user; only current user's or global) -----


@app.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """List notifications for current user (and global). Includes audio_url when reminder voice is available."""
    if limit < 1 or limit > 100:
        limit = 50
    if offset < 0:
        offset = 0
    rows = get_notifications_for_user(current_user["id"], limit=limit, offset=offset)
    items = [
        NotificationItem(
            id=r["id"],
            user_id=r.get("user_id"),
            title=r.get("title", ""),
            body=r.get("body", ""),
            source=r.get("source", "reminder"),
            created_at=r.get("created_at"),
            audio_url=f"/notifications/audio/{r['id']}" if r.get("audio_path") else None,
        )
        for r in rows
    ]
    return NotificationListResponse(items=items)


@app.get("/notifications/audio/{notification_id}")
def get_notification_audio(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Stream reminder voice WAV (Murf TTS). Only allowed if notification belongs to current user or is global (user_id IS NULL)."""
    from app.db import get_notification_for_user
    row = get_notification_for_user(notification_id, current_user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found or access denied.")
    path_str = row.get("audio_path")
    if not path_str:
        raise HTTPException(status_code=404, detail="No audio for this notification.")
    path = Path(path_str)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(path, media_type="audio/wav")


# ----- Daily brief (per-user; only current user's brief) -----


@app.get("/brief", response_model=BriefResponse)
def get_brief(
    current_user: dict = Depends(get_current_user),
):
    """Get today's daily brief (text and optional audio URL). Generates on first request if missing."""
    from datetime import date
    brief_date = date.today().isoformat()
    row = get_daily_brief(current_user["id"], brief_date)
    if row and row.get("text_content"):
        audio_url = None
        if row.get("audio_path"):
            audio_url = f"/brief/audio?date={brief_date}"
        return BriefResponse(
            text=row["text_content"],
            audio_url=audio_url,
            brief_date=brief_date,
        )
    # Generate now
    try:
        text, audio_path = generate_brief_for_user(
            current_user["id"],
            user_name=current_user.get("name"),
        )
        upsert_daily_brief(current_user["id"], brief_date, text, audio_path=audio_path)
        return BriefResponse(
            text=text,
            audio_url=f"/brief/audio?date={brief_date}" if audio_path else None,
            brief_date=brief_date,
        )
    except Exception as e:
        logger.exception("Brief generation failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate brief.")


@app.get("/brief/audio")
def get_brief_audio(
    date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Stream today's brief WAV (Murf TTS). Optional query date=YYYY-MM-DD."""
    from datetime import date as date_type
    brief_date = date or date_type.today().isoformat()
    row = get_daily_brief(current_user["id"], brief_date)
    if not row or not row.get("audio_path"):
        raise HTTPException(status_code=404, detail="No audio for this date.")
    path = Path(row["audio_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(path, media_type="audio/wav")


# ----- Internal (cron / worker; optional INTERNAL_SECRET) -----


def _require_internal_secret(request: Request) -> None:
    """Raise 401 if INTERNAL_SECRET is set and request does not provide it."""
    secret = get_settings().internal_secret
    if not secret:
        return
    provided = request.headers.get("X-Internal-Secret") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if provided != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing internal secret.")


@app.post("/internal/reminders/process")
def internal_process_reminders(request: Request):
    """Process due reminders (call from cron or external worker). Requires X-Internal-Secret if INTERNAL_SECRET is set."""
    _require_internal_secret(request)
    from app.utils.reminder_worker import _process_due_reminders
    _process_due_reminders()
    return {"status": "ok", "message": "Processed due reminders."}


# ----- Public / health / admin -----

@app.get("/")
def root():
    return FileResponse(get_settings().base_dir / "static" / "index.html")


@app.get("/health")
def health():
    """Simple health (backward compatible)."""
    return {"status": "ok"}


@app.get("/health/live")
def health_live():
    """Liveness: process is up."""
    return check_live()


@app.get("/health/ready")
def health_ready():
    """Readiness: DB and critical deps reachable."""
    return check_ready()


# ----- Admin dashboard (admin-only: email in ADMIN_EMAILS) -----

@app.get("/admin/dashboard/config", response_model=AdminDashboardConfigResponse)
def admin_dashboard_config():
    """Non-secret config for dashboard (e.g. same-origin API). No auth required for loading login page."""
    return AdminDashboardConfigResponse(api_base_url="/")


@app.get("/admin/status")
def admin_status(admin_user: dict = Depends(get_current_admin_user)):
    """System status: Groq keys, vector store. Admin only."""
    groq = ops_state.get_groq_key_status()
    vector = ops_state.get_vector_store_status()
    return {
        "service": "JarvisAI",
        "groq": {
            "last_used_key_suffix": groq.get("last_used_key_suffix"),
            "last_used_at": groq.get("last_used_at"),
            "keys_in_rotation": groq.get("keys_in_rotation", 0),
            "rate_limit_note": "Groq limits are per-key; rotation spreads load.",
        },
        "vector_store": {
            "doc_count": vector.get("doc_count", 0),
            "last_rebuild_time": vector.get("last_rebuild_time"),
            "index_path": vector.get("index_path", ""),
        },
    }


@app.get("/admin/usage", response_model=AdminUsageResponse)
def admin_usage(
    hours: int = 24,
    admin_user: dict = Depends(get_current_admin_user),
):
    """Aggregated usage from request logs (last N hours). Admin only."""
    if hours < 1 or hours > 168:
        hours = 24
    data = log_usage.aggregate_usage(hours=hours)
    data["log_file_available"] = log_usage.log_file_available()
    return AdminUsageResponse(**data)


@app.get("/admin/requests", response_model=AdminRequestsResponse)
def admin_requests(
    limit: int = 50,
    offset: int = 0,
    admin_user: dict = Depends(get_current_admin_user),
):
    """Recent requests from log file (paginated). Admin only."""
    if limit < 1 or limit > 200:
        limit = 50
    if offset < 0:
        offset = 0
    rows = log_usage.recent_requests(limit=limit, offset=offset)
    return AdminRequestsResponse(
        items=[AdminRequestRow(**r) for r in rows],
        log_file_available=log_usage.log_file_available(),
    )


# Serve admin dashboard SPA (login + status + usage + requests)
_admin_dir = get_settings().base_dir / "static" / "admin"


@app.get("/admin/dashboard", include_in_schema=False)
def admin_dashboard_redirect():
    """Redirect to dashboard SPA (trailing slash for StaticFiles index)."""
    return RedirectResponse(url="/admin/dashboard/", status_code=302)


if _admin_dir.exists():
    app.mount("/admin/dashboard", StaticFiles(directory=str(_admin_dir), html=True), name="admin_dashboard")

app.mount("/static", StaticFiles(directory=str(get_settings().base_dir / "static")), name="static")
