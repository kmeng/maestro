"""Tests for the Web UI HTTP server: health, version, content-type, and 404 behavior."""

from fastapi.testclient import TestClient

import maestro
from maestro.webui import app

client = TestClient(app)


def test_health_returns_200_and_status_ok():
    """GET /health returns 200 and exact body {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_returns_200_and_version_field():
    """GET /version returns 200 and body with non-empty version string."""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str) and data["version"] != ""


def test_version_endpoint_matches_package_version():
    """GET /version body's version field equals maestro.__version__ (single source of truth)."""
    response = client.get("/version")
    assert response.json()["version"] == maestro.__version__


def test_health_response_is_json():
    """Content-Type header starts with application/json."""
    response = client.get("/health")
    assert response.headers["content-type"].startswith("application/json")


def test_unknown_route_returns_404():
    """GET /does-not-exist returns 404 to confirm no catch-all."""
    response = client.get("/does-not-exist")
    assert response.status_code == 404
