"""Unit tests for the live execution-flow view route (T3.8, Epic 3).

Tests the skeleton render only — SSE streaming is covered by T3.10 curl smoke.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maestro.webui.live_view import router as live_router


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(live_router)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def test_live_route_registered_and_renders_skeleton(client):
    response = client.get("/live")
    assert response.status_code == 200
    body = response.text
    assert "实时调度" in body
    assert "进行中" in body
    assert "最近完成" in body
    assert "暂无进行中的调度" in body
    assert "暂无已完成的调度" in body


def test_live_renders_status_banner(client):
    response = client.get("/live")
    body = response.text
    assert '<div id="status" class="status-banner connecting">连接中…</div>' in body


def test_live_subscribes_to_correct_sse_url(client):
    response = client.get("/live")
    body = response.text
    assert "new EventSource('/api/dispatch_log/stream')" in body


def test_live_has_rotated_handler(client):
    response = client.get("/live")
    body = response.text
    assert "addEventListener('rotated'" in body


def test_live_response_is_html_utf8(client):
    response = client.get("/live")
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("text/html")
    body = response.text
    assert "实时调度" in body
    assert "进行中" in body
    assert "已连接" in body
    assert "utf-8" in content_type.lower()
