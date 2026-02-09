"""Repository protocols (interfaces) for testability and clear boundaries."""
from typing import List, Optional, Protocol, Tuple


class UserRepository(Protocol):
    """User persistence: get by id/email, create."""

    def get_by_id(self, user_id: int) -> Optional[dict]:
        """Return user row (id, email, password_hash, name, ...) or None."""
        ...

    def get_by_email(self, email: str) -> Optional[dict]:
        """Return user row including password_hash, or None."""
        ...

    def create(self, email: str, password_hash: str, name: str = "") -> int:
        """Insert user; return new id. Raises on duplicate email."""
        ...


class ChatSessionRepository(Protocol):
    """Per-user chat session persistence: list, get history, append, get_or_create session id."""

    def get_or_create_session_id(self, user_id: int, session_id: Optional[str] = None) -> str:
        """Return existing session_id if valid, else new uuid."""
        ...

    def get_history(self, user_id: int, session_id: str) -> List[dict]:
        """Load message list for session (user-scoped)."""
        ...

    def append_message(self, user_id: int, session_id: str, role: str, content: str) -> None:
        """Append one message and persist (user-scoped)."""
        ...

    def list_sessions(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> Tuple[List[dict], int]:
        """List sessions for user (newest first). Returns (items, total_count)."""
        ...
