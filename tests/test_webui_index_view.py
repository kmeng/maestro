from fastapi.testclient import TestClient
from maestro.webui import app


def test_index_renders_overview_skeleton():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert 'class="page-h1">Overview</h1>' in body
    assert 'id="kpi-today-dispatches"' in body
    assert 'id="kpi-cumulative-savings"' in body
    assert 'id="kpi-active-workers"' in body
    assert 'id="kpi-open-problems"' in body
    assert 'id="sparkline"' in body
    assert 'id="now-running-body"' in body
    for href in ["/team", "/scaffold", "/live", "/history", "/savings", "/problems"]:
        assert f'href="{href}"' in body
    assert 'class="sidebar"' in body
    assert "/api/overview" in body


def test_index_no_inline_style_block():
    client = TestClient(app)
    r = client.get("/")
    assert "<style>" not in r.text
