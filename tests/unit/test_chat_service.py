"""Unit tests for ChatService with mocked repository and external services."""
from unittest.mock import MagicMock, patch

import pytest

from app.services.chat_service import ChatService
from app.repositories.protocols import ChatSessionRepository


@pytest.fixture
def mock_chat_repo():
    repo = MagicMock(spec=ChatSessionRepository)
    repo.get_or_create_session_id.return_value = "sess-1"
    repo.get_history.return_value = []
    repo.append_message = MagicMock()
    repo.list_sessions.return_value = ([], 0)
    return repo


def test_chat_service_get_or_create_session_id(mock_chat_repo):
    """ChatService delegates get_or_create_session_id to repo."""
    svc = ChatService(mock_chat_repo)
    sid = svc.get_or_create_session_id(1, None)
    assert sid == "sess-1"
    mock_chat_repo.get_or_create_session_id.assert_called_once_with(1, None)


def test_chat_service_list_sessions(mock_chat_repo):
    """ChatService delegates list_sessions to repo."""
    mock_chat_repo.list_sessions.return_value = ([{"session_id": "s1", "message_count": 2}], 1)
    svc = ChatService(mock_chat_repo)
    items, total = svc.list_sessions(1, limit=10, offset=0)
    assert total == 1
    assert len(items) == 1
    assert items[0]["session_id"] == "s1"
    mock_chat_repo.list_sessions.assert_called_once_with(1, limit=10, offset=0)


def test_chat_service_chat_general_returns_reply_and_persists(mock_chat_repo):
    """chat_general returns LLM reply and appends user + assistant messages to repo."""
    with patch("app.services.chat_service.VectorStore") as vs_class:
        with patch("app.services.chat_service.GroqService") as groq:
            vs_class.return_value.get_memory_context_for_query.return_value = ""
            groq.chat_general.return_value = "Hello back"
            svc = ChatService(mock_chat_repo)
            reply = svc.chat_general(1, "sess-1", "Hi")
            assert reply == "Hello back"
            mock_chat_repo.append_message.assert_any_call(1, "sess-1", "user", "Hi")
            mock_chat_repo.append_message.assert_any_call(1, "sess-1", "assistant", "Hello back")


def test_chat_service_chat_realtime_returns_reply_and_persists(mock_chat_repo):
    """chat_realtime returns (reply, tool_used) and appends messages."""
    with patch("app.services.chat_service.VectorStore") as vs_class:
        with patch("app.services.chat_service.RealtimeService") as realtime:
            vs_class.return_value.get_memory_context_for_query.return_value = ""
            realtime.chat.return_value = ("Realtime answer", "tavily")
            svc = ChatService(mock_chat_repo)
            reply, tool = svc.chat_realtime(1, "sess-1", "What is weather?", search_query=None)
            assert reply == "Realtime answer"
            assert tool == "tavily"
            mock_chat_repo.append_message.assert_any_call(1, "sess-1", "user", "What is weather?")
            mock_chat_repo.append_message.assert_any_call(1, "sess-1", "assistant", "Realtime answer")
