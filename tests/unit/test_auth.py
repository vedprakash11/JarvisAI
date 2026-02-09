"""Unit tests for auth: password hashing, JWT, get_current_user behavior."""
import pytest
from unittest.mock import patch, MagicMock

from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    get_current_user,
)
from app.repositories.protocols import UserRepository


def test_hash_password_and_verify():
    """Hashing and verifying password round-trips correctly."""
    plain = "secret123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_token():
    """Create token and decode returns subject."""
    with patch("app.auth.config") as cfg:
        cfg.JWT_SECRET = "test-secret"
        cfg.JWT_ALGORITHM = "HS256"
        token = create_access_token("42")
        assert token
        sub = decode_token(token)
        assert sub == "42"


def test_decode_token_invalid_returns_none():
    """Invalid or malformed token returns None."""
    assert decode_token("bad") is None
    assert decode_token("") is None


@pytest.mark.asyncio
async def test_get_current_user_missing_credentials_raises():
    """Missing Authorization header raises 401."""
    from fastapi import HTTPException

    credentials = MagicMock()
    credentials.credentials = None
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials, user_repo=MagicMock())
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises():
    """Invalid token raises 401."""
    from fastapi import HTTPException

    credentials = MagicMock()
    credentials.credentials = "invalid-jwt"
    with patch("app.auth.decode_token", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, user_repo=MagicMock())
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_not_found_raises():
    """Valid token but user not in repo raises 401."""
    from fastapi import HTTPException

    credentials = MagicMock()
    credentials.credentials = "any"
    repo = MagicMock(spec=UserRepository)
    repo.get_by_id.return_value = None
    with patch("app.auth.decode_token", return_value="999"):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, user_repo=repo)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_returns_user_with_admin_flag():
    """Valid token and user in repo returns user dict with is_admin."""
    credentials = MagicMock()
    credentials.credentials = "token"
    repo = MagicMock(spec=UserRepository)
    repo.get_by_id.return_value = {
        "id": 1,
        "email": "admin@test.com",
        "name": "Admin",
    }
    with patch("app.auth.decode_token", return_value="1"):
        with patch("app.auth.get_settings") as get_settings:
            get_settings.return_value.admin_emails = ["admin@test.com"]
            user = await get_current_user(credentials=credentials, user_repo=repo)
    assert user["id"] == 1
    assert user["email"] == "admin@test.com"
    assert user["name"] == "Admin"
    assert user["is_admin"] is True
