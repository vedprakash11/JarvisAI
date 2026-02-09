"""
Pydantic data models for API request/response and error schema.
"""
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Single error detail (e.g. field-level)."""

    code: str = Field(..., description="Error code or field name")
    message: str = Field(..., description="Human-readable message")


class ErrorResponse(BaseModel):
    """Structured error response for 4xx/5xx."""

    code: str = Field(..., description="Application error code")
    message: str = Field(..., description="Human-readable summary")
    details: Optional[List[ErrorDetail]] = Field(None, description="Optional per-field or extra details")


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    name: str = Field("", max_length=255)


class UserInfo(BaseModel):
    """Current user info (no secrets)."""

    id: int
    email: str
    name: str = ""
    is_admin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


# Max lengths for validation and docs (do not log full message body)
MESSAGE_MAX_LENGTH = 32_000
SEARCH_QUERY_MAX_LENGTH = 2_000
SESSION_ID_MAX_LENGTH = 128


class ChatRequest(BaseModel):
    """Request body for chat endpoints. Limits: message 32k chars, search_query 2k, session_id 128."""
    message: str = Field(..., min_length=1, max_length=MESSAGE_MAX_LENGTH, description="User message")
    session_id: Optional[str] = Field(None, max_length=SESSION_ID_MAX_LENGTH, description="Session ID for conversation continuity")
    search_query: Optional[str] = Field(None, max_length=SEARCH_QUERY_MAX_LENGTH, description="Optional query for realtime search (defaults to message)")


class ChatResponse(BaseModel):
    """Response for chat endpoints."""
    reply: str
    session_id: str


class RebuildRequest(BaseModel):
    """Optional body for rebuild endpoint."""
    pass


class SessionSummary(BaseModel):
    session_id: str
    message_count: int
    preview: Optional[str] = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[dict]


class SessionListResponse(BaseModel):
    """Paginated list of chat sessions."""

    items: List[SessionSummary] = Field(..., description="Sessions for this page")
    total: int = Field(..., ge=0, description="Total number of sessions")


# ----- Admin dashboard -----


class AdminUsageResponse(BaseModel):
    """Aggregated usage stats from request logs (admin only)."""

    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    by_mode: dict = Field(default_factory=dict)
    by_status: dict = Field(default_factory=dict)
    by_hour: dict = Field(default_factory=dict)
    sorted_hours: List[tuple] = Field(default_factory=list)
    sorted_latency_buckets: List[tuple] = Field(default_factory=list)
    avg_latency_ms: float = 0.0
    latency_samples: int = 0
    log_file_available: bool = True


class AdminRequestRow(BaseModel):
    """Single row for recent requests table (admin only)."""

    path: str
    method: str
    client_ip: str
    status_code: Optional[int] = None
    latency_ms: Optional[float] = None
    mode: str
    session_id: str
    timestamp: str


class AdminRequestsResponse(BaseModel):
    """Paginated recent requests (admin only)."""

    items: List[AdminRequestRow] = Field(default_factory=list)
    log_file_available: bool = True


class AdminDashboardConfigResponse(BaseModel):
    """Non-secret config for dashboard frontend (e.g. API base URL for display)."""

    api_base_url: str = "/"


# ----- Reminders & brief -----


class ReminderCreate(BaseModel):
    """Create a reminder: either in_minutes or run_at (ISO datetime)."""

    message: str = Field(..., min_length=1, max_length=2000)
    in_minutes: Optional[int] = Field(None, ge=1, le=43200)  # up to 30 days
    run_at: Optional[str] = None  # ISO datetime if no in_minutes


class ReminderItem(BaseModel):
    id: int
    user_id: int
    message: str
    run_at: Any
    status: str
    created_at: Any


class ReminderListResponse(BaseModel):
    items: List[ReminderItem]
    total: int


class BriefResponse(BaseModel):
    """Daily brief text and optional audio URL."""

    text: str
    audio_url: Optional[str] = None
    brief_date: str


class NotificationItem(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    body: str
    source: str
    created_at: Any
    audio_url: Optional[str] = None  # set when audio_path is present


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
