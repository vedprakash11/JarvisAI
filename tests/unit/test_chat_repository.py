"""Unit tests for FileChatSessionRepository."""

from app.repositories.chat_repository import FileChatSessionRepository


def test_file_chat_repo_list_sessions_empty(tmp_path):
    """List sessions when user has no chats returns empty."""
    repo = FileChatSessionRepository()
    repo._base = tmp_path
    items, total = repo.list_sessions(999, limit=10, offset=0)
    assert items == []
    assert total == 0


def test_file_chat_repo_append_and_history(tmp_path):
    """Append message and get_history return correct data."""
    repo = FileChatSessionRepository()
    repo._base = tmp_path
    session_id = repo.get_or_create_session_id(1, None)
    assert session_id
    repo.append_message(1, session_id, "user", "Hello")
    repo.append_message(1, session_id, "assistant", "Hi")
    history = repo.get_history(1, session_id)
    assert len(history) == 2
    assert history[0]["role"] == "user" and history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant" and history[1]["content"] == "Hi"
    items, total = repo.list_sessions(1, limit=50, offset=0)
    assert total == 1
    assert items[0]["session_id"] == session_id
    assert items[0]["message_count"] == 2
