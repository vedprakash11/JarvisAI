# JarvisAI Architecture

## How to run

```bash
pip install -r requirements.txt && python run.py   # API (port 8000)
python run_dashboard.py                             # Admin dashboard (port 5000)
```

## Overview

JarvisAI is a FastAPI application with a **layered architecture**: API → Service → Repository. Business logic lives in services; routes are thin and use dependency injection for testability.

## Layers

### 1. API (routes)

- **Location:** `app/main.py`
- **Responsibility:** HTTP handling, request/response models, auth dependency, rate limiting. No business logic.
- **Dependencies:** `get_current_user`, `get_user_repository`, `get_chat_service` (from app.state), settings.

### 2. Services

- **ChatService** (`app/services/chat_service.py`): Orchestrates chat sessions (via `ChatSessionRepository`), vector store (RAG), and LLM (GroqService, RealtimeService). Single place for general/realtime chat flows.
- **GroqService** (`app/services/groq_service.py`): Groq LLM with multi-key rotation, system prompt, and RAG context.
- **RealtimeService** (`app/services/realtime_service.py`): Tavily web search + Groq for up-to-date answers.
- **VectorStore** (`app/services/vector_store.py`): FAISS index over `database/learning_data/*.txt` and conversation memory; similarity search and newest-first context.

### 3. Repositories (data access)

- **Protocols:** `app/repositories/protocols.py` — `UserRepository`, `ChatSessionRepository` (interfaces).
- **Implementations:**
  - **MySQLUserRepository** (`app/repositories/user_repository.py`): Delegates to `app.db` (MySQL). Used for auth (register, login, get_current_user).
  - **FileChatSessionRepository** (`app/repositories/chat_repository.py`): Per-user chat sessions under `database/chats_data/{user_id}/{session_id}.json`. Used by ChatService.

Services depend on repository **abstractions**, not concrete DB or file implementations, so tests can inject in-memory or mock implementations.

### 3b. Service protocols (external dependencies)

- **Protocols:** `app/services/protocols.py` — `LLMProvider`, `SearchProvider`, `VectorStoreProvider`.
- **Implementations:** GroqService (LLM), Tavily in RealtimeService (search), VectorStore (FAISS + embeddings). ChatService uses these via concrete classes today; they can be swapped for mocks in tests.

### 4. Core

- **Settings** (`app/core/settings.py`): Pydantic Settings from `.env`; single source of truth, validated at startup.
- **Health** (`app/core/health.py`): Liveness (`/health/live`) and readiness (`/health/ready` with DB check).
- **Config facade** (`config.py`): Exposes settings as module-level constants for backward compatibility.

## Data flow

- **Auth:** `POST /auth/register` or `POST /auth/login` → UserRepository (create / get_by_email) → JWT returned. Protected routes use `get_current_user` (JWT → UserRepository.get_by_id).
- **Chat:** Protected `POST /chat/general` or `POST /chat/realtime` → ChatService (get_or_create_session_id, get_history, LLM call, append_message, vector_store.add_memory) → ChatSessionRepository + VectorStore + Groq/Tavily.
- **Sessions list:** `GET /chats/sessions` → ChatService.list_sessions (delegates to ChatSessionRepository with limit/offset) → paginated `SessionListResponse`.
- **Reminders, notifications, daily brief:** All use `get_current_user` (any authenticated user). Reminders and daily_briefs tables are keyed by `user_id`; notifications are filtered by `user_id` or global (`user_id IS NULL`). No user can read or access another user’s data; notification audio is served only via `get_notification_for_user(id, current_user["id"])`.

## Where to add features

- **New API endpoint:** Add route in `app/main.py`, keep handler thin; call a service or repository via Depends.
- **New business rule (e.g. chat):** Implement in `ChatService` or a new service; inject repositories and config.
- **New data source:** Add a repository protocol in `app/repositories/protocols.py`, implement it, register in `app/deps.py` and use in lifespan or Depends.
- **New config:** Add field to `app/core/settings.py` and (optionally) to `config.py` facade.

## Startup

1. **Lifespan** runs: `init_db()` (create DB/table if needed), then create `FileChatSessionRepository` and `ChatService`, load or build FAISS vector store, set `app.state.chat_service`.
2. All chat routes use the same `ChatService` instance via `get_chat_service(request)`.

## Admin dashboard

- **Location:** SPA in `static/admin/` (index.html, admin.js, admin.css), served at `/admin/dashboard/` by FastAPI StaticFiles.
- **Access:** Only users whose email is in `ADMIN_EMAILS` (env, comma-separated). `GET /me` returns `is_admin: true/false`; admin routes use `get_current_admin_user` (403 if not admin).
- **Data sources:** `GET /admin/status` (Groq + vector store from `ops_state`), `GET /admin/usage` and `GET /admin/requests` (from request log file via `app/utils/log_usage.py`). Log file path comes from `LOG_FILE` (same as main app).
- **Adding panels:** Add a new admin-only route in `app/main.py` (e.g. `GET /admin/xyz`) and consume it in `static/admin/admin.js`; show loading/error states in the UI.

## Observability and security

- **Structured logging:** JSON lines with `request_id`, `path`, `method`, `client_ip`, `status_code`, `latency_ms`, and for chat routes `session_id`, `mode`. Log sink is configurable via `LOG_FILE` (file or stderr). **Secrets are never logged:** no passwords, tokens, or full message bodies; only truncated query for support. See `app/utils/request_logger.py`.
- **Request ID:** Set in middleware (or from client `X-Request-ID`), added to every response header and to 4xx/5xx error body as `request_id` when available.
- **Security headers:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`. CORS is configurable in `app/main.py` (allow_origins); document trusted origins for production.
- **Errors:** 4xx/5xx return structured body `{ "code", "message", "details", "request_id"? }`. Validation errors (422) include field-level detail.
- **Rate limiting:** Chat endpoints (`POST /chat/general`, `POST /chat/realtime`) use SlowAPI per IP; default `30/minute`, configurable via `RATE_LIMIT_CHAT`. When exceeded, response is 429 with structured error body.
- **Input limits:** Request body validated with Pydantic; `message` max 32k chars, `search_query` max 2k, `session_id` max 128. See `app/models.py`.

## Health and readiness

- **Liveness** (`GET /health/live`): Process is up; no dependency checks.
- **Readiness** (`GET /health/ready`): Database is reachable (`SELECT 1`). Returns `200` with `"database": "up"` when OK; `200` with `"database": "down"` when DB is unavailable (so orchestrators can keep sending traffic or not depending on policy). Optional: vector store or other deps can be added to readiness later.
