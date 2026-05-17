from fastapi.testclient import TestClient
from maestro.webui import app


def test_live_extends_base_with_zones_skeleton():
    client = TestClient(app)
    r = client.get("/live")
    assert r.status_code == 200
    body = r.text
    assert 'class="sidebar"' in body
    assert 'class="page-h1">实时调度</h1>' in body
    assert 'id="status"' in body
    assert 'id="running"' in body
    assert 'id="completed"' in body
    assert 'EventSource' in body
    assert '/api/dispatch_log/stream' in body
    assert ".card" in body or ".zone" in body
