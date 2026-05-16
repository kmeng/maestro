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


def test_index_returns_200_html():
    """GET / returns 200 and content type is text/html."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_index_contains_overview_skeleton():
    """GET / body contains the Overview-page structural markers.

    Epic 9 / T9.3 replaced the legacy hero copy ("等待第一支乐章 · 本地 AI 软件团队")
    with the Dashboard Cockpit Overview page driven by /api/overview. The
    old hero strings are retired; assert the new page's skeleton instead.
    """
    response = client.get("/")
    body = response.text
    assert 'class="page-h1">Overview</h1>' in body
    assert "/api/overview" in body


def test_index_loads_vendored_htmx():
    """GET / body contains the vendored htmx script path."""
    response = client.get("/")
    assert "/static/vendor/htmx.min.js" in response.text


def test_index_renders_running_version():
    """GET / body contains the running version string (maestro.__version__)."""
    response = client.get("/")
    assert maestro.__version__ in response.text


def test_static_htmx_served():
    """GET /static/vendor/htmx.min.js returns 200 and JavaScript content type."""
    response = client.get("/static/vendor/htmx.min.js")
    assert response.status_code == 200
    ct = response.headers["content-type"]
    assert ct.startswith("application/javascript") or ct.startswith("text/javascript")
