"""
Session and conversation management.
Uses ChatSessionRepository for persistence; VectorStore + Groq/Realtime for LLM.
"""
import logging
from typing import List, Optional, Tuple

from app.repositories.protocols import ChatSessionRepository
from app.services.vector_store import VectorStore
from app.services.groq_service import GroqService
from app.services.realtime_service import RealtimeService

logger = logging.getLogger(__name__)


class ChatService:
    """Manages chat sessions (via repository) and LLM flows (vector store + Groq/Tavily)."""

    def __init__(self, chat_repo: ChatSessionRepository) -> None:
        self._chat_repo = chat_repo
        self.vector_store = VectorStore()

    def get_or_create_session_id(self, user_id: int, session_id: Optional[str] = None) -> str:
        return self._chat_repo.get_or_create_session_id(user_id, session_id)

    def get_history(self, user_id: int, session_id: str) -> List[dict]:
        return self._chat_repo.get_history(user_id, session_id)

    def append_message(self, user_id: int, session_id: str, role: str, content: str) -> None:
        self._chat_repo.append_message(user_id, session_id, role, content)

    def list_sessions(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> Tuple[List[dict], int]:
        return self._chat_repo.list_sessions(user_id, limit=limit, offset=offset)

    def chat_general(self, user_id: int, session_id: str, message: str) -> str:
        session_id = self.get_or_create_session_id(user_id, session_id)
        try:
            stored_context = self.vector_store.get_memory_context_for_query(message, user_id, k=6)
        except Exception:
            stored_context = ""
        history = self.get_history(user_id, session_id)
        reply = GroqService.chat_general(message, history, stored_context=stored_context)
        try:
            self.append_message(user_id, session_id, "user", message)
            self.append_message(user_id, session_id, "assistant", reply)
            self._save_to_memory(user_id, message, reply)
        except Exception as e:
            logger.warning("Failed to persist message or memory: %s", e)
        return reply

    def chat_realtime(
        self,
        user_id: int,
        session_id: str,
        message: str,
        search_query: Optional[str] = None,
    ) -> tuple[str, str]:
        """Returns (reply, tool_used) where tool_used is 'openweather' | 'tavily' | 'llm answer'."""
        session_id = self.get_or_create_session_id(user_id, session_id)
        stored_context = self.vector_store.get_memory_context_for_query(message, user_id, k=6)
        history = self.get_history(user_id, session_id)
        reply, tool_used = RealtimeService.chat(
            message, history, search_query=search_query, stored_context=stored_context
        )
        self.append_message(user_id, session_id, "user", message)
        self.append_message(user_id, session_id, "assistant", reply)
        self._save_to_memory(user_id, message, reply)
        return reply, tool_used

    def _save_to_memory(self, user_id: int, user_message: str, assistant_reply: str) -> None:
        try:
            self.vector_store.add_memory(user_id, user_message, assistant_reply)
        except Exception:
            pass

    def rebuild_vector_store(self) -> None:
        self.vector_store.build()
