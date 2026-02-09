"""FastAPI dependency injection: settings, repositories, services."""
from typing import Annotated

from fastapi import Depends

from app.core.settings import Settings, get_settings
from app.repositories import FileChatSessionRepository, MySQLUserRepository
from app.repositories.protocols import ChatSessionRepository, UserRepository
from app.services.chat_service import ChatService


def get_settings_dep() -> Settings:
    return get_settings()


def get_user_repository() -> UserRepository:
    return MySQLUserRepository()


def get_chat_repository() -> ChatSessionRepository:
    return FileChatSessionRepository()


def get_chat_service(
    chat_repo: Annotated[ChatSessionRepository, Depends(get_chat_repository)],
) -> ChatService:
    return ChatService(chat_repo)
