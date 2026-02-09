"""File-based implementation of ChatSessionRepository: database/chats_data/{user_id}/{session_id}.json"""
import json
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.settings import get_settings


class FileChatSessionRepository:
    """Per-user chat sessions stored as JSON files under chats_data/{user_id}/."""

    def __init__(self) -> None:
        self._base = get_settings().chats_data_dir

    def _user_dir(self, user_id: int) -> Path:
        return self._base / str(user_id)

    def _chat_file(self, user_id: int, session_id: str) -> Path:
        return self._user_dir(user_id) / f"{session_id}.json"

    def get_or_create_session_id(self, user_id: int, session_id: Optional[str] = None) -> str:
        if session_id and self._chat_file(user_id, session_id).exists():
            return session_id
        return str(uuid.uuid4())

    def get_history(self, user_id: int, session_id: str) -> List[dict]:
        path = self._chat_file(user_id, session_id)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("messages", [])
        except Exception:
            return []

    def append_message(self, user_id: int, session_id: str, role: str, content: str) -> None:
        history = self.get_history(user_id, session_id)
        history.append({"role": role, "content": content})
        path = self._chat_file(user_id, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"messages": history}, f, ensure_ascii=False, indent=2)

    def list_sessions(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> Tuple[List[dict], int]:
        dir_path = self._user_dir(user_id)
        if not dir_path.exists():
            return [], 0
        all_files = sorted(
            dir_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        total = len(all_files)
        out: List[dict] = []
        for f in all_files[offset : offset + limit]:
            session_id = f.stem
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                messages = data.get("messages", [])
                preview = None
                if messages:
                    first = messages[0]
                    content = first.get("content") or ""
                    preview = content[:60] + ("..." if len(content) > 60 else "")
                out.append({"session_id": session_id, "message_count": len(messages), "preview": preview})
            except Exception:
                out.append({"session_id": session_id, "message_count": 0, "preview": None})
        return out, total
