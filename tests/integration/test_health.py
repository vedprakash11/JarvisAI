"""Integration tests: health and root endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_live(client: TestClient):
    r = client.get("/health/live")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok" and data.get("check") == "live"


def test_health_ready(client: TestClient):
    r = client.get("/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert "check" in data and data["check"] == "ready"
    assert "database" in data


def test_root_serves_html(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_request_id_in_response(client: TestClient):
    r = client.get("/health")
    assert "x-request-id" in [h.lower() for h in r.headers]
    # Or client may send X-Request-ID and we echo it
    assert r.status_code == 200
