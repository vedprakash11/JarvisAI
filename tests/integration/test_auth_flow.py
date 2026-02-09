"""Integration tests for auth: register, login, /me with in-memory user repository."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.deps import get_user_repository
from tests.conftest import InMemoryUserRepository


@pytest.fixture
def in_memory_user_repo():
    return InMemoryUserRepository()


@pytest.fixture
def client_auth(in_memory_user_repo):
    """Client with user repository overridden to in-memory; db_available patched for register."""
    app.dependency_overrides[get_user_repository] = lambda: in_memory_user_repo
    try:
        with patch("app.main.db_available", True):
            yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_user_repository, None)


def test_register_login_me_flow(client_auth: TestClient):
    """Register a user, login, then GET /me returns the user."""
    # Register
    r = client_auth.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "pass1234", "name": "Test User"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["name"] == "Test User"
    token = data["access_token"]

    # Login (with same user)
    r2 = client_auth.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "pass1234"},
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["email"] == "test@example.com"

    # Me with token
    r3 = client_auth.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 200
    me = r3.json()
    assert me["email"] == "test@example.com"
    assert "id" in me


def test_me_unauthorized_without_token(client_auth: TestClient):
    """GET /me without token returns 401."""
    r = client_auth.get("/me")
    assert r.status_code == 401


def test_register_duplicate_email_returns_400(client_auth: TestClient):
    """Registering the same email twice returns 400."""
    payload = {"email": "dup@example.com", "password": "pass1234", "name": "First"}
    r1 = client_auth.post("/auth/register", json=payload)
    assert r1.status_code == 200
    r2 = client_auth.post("/auth/register", json=payload)
    assert r2.status_code == 400
    assert "already" in (r2.json().get("message") or r2.json().get("detail") or "").lower()
