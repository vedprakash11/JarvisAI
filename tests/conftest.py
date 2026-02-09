"""
Pytest fixtures: app, client, mock repositories for unit/integration tests.
"""
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on path and .env is loaded
import config  # noqa: F401

from app.main import app, get_chat_service
from app.repositories.protocols import ChatSessionRepository, UserRepository


class InMemoryUserRepository(UserRepository):
    """In-memory user store for tests."""

    def __init__(self) -> None:
        self._users: dict = {}  # id -> dict; email -> id index
        self._next_id = 1

    def get_by_id(self, user_id: int) -> Optional[dict]:
        return self._users.get(user_id)

    def get_by_email(self, email: str) -> Optional[dict]:
        email = email.strip().lower()
        for u in self._users.values():
            if u["email"] == email:
                return u
        return None

    def create(self, email: str, password_hash: str, name: str = "") -> int:
        email = email.strip().lower()
        for u in self._users.values():
            if u["email"] == email:
                raise ValueError("Duplicate email")
        uid = self._next_id
        self._next_id += 1
        self._users[uid] = {
            "id": uid,
            "email": email,
            "password_hash": password_hash,
            "name": (name or "")[:255],
        }
        return uid


class InMemoryChatRepository(ChatSessionRepository):
    """In-memory chat sessions for tests."""

    def __init__(self) -> None:
        self._sessions: dict = {}  # (user_id, session_id) -> list of messages

    def _key(self, user_id: int, session_id: str) -> tuple:
        return (user_id, session_id)

    def get_or_create_session_id(self, user_id: int, session_id: Optional[str] = None) -> str:
        import uuid
        if session_id and self._key(user_id, session_id) in self._sessions:
            return session_id
        return str(uuid.uuid4())

    def get_history(self, user_id: int, session_id: str) -> List[dict]:
        return self._sessions.get(self._key(user_id, session_id), [])[:]

    def append_message(self, user_id: int, session_id: str, role: str, content: str) -> None:
        k = self._key(user_id, session_id)
        if k not in self._sessions:
            self._sessions[k] = []
        self._sessions[k].append({"role": role, "content": content})

    def list_sessions(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> Tuple[List[dict], int]:
        keys = [k for k in self._sessions if k[0] == user_id]
        total = len(keys)
        keys = keys[offset : offset + limit]
        out = []
        for (_, sid) in keys:
            msgs = self._sessions[(user_id, sid)]
            preview = (msgs[0].get("content") or "")[:60] if msgs else None
            if preview and len(msgs[0].get("content") or "") > 60:
                preview += "..."
            out.append({"session_id": sid, "message_count": len(msgs), "preview": preview})
        return out, total


@pytest.fixture
def app_with_mocks():
    """App with overridden dependencies not used for TestClient (lifespan sets chat_service)."""
    return app


@pytest.fixture
def client(app_with_mocks):
    """TestClient; uses real lifespan (init_db, vector store). For isolated tests use override_dep."""
    return TestClient(app_with_mocks)


@pytest.fixture
def temp_chat_dir():
    """Temporary directory for file-based chat repo tests."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)
