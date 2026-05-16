from fastapi.testclient import TestClient
from maestro.webui import app


def test_history_extends_base_empty_state():
    client = TestClient(app)
    r = client.get("/history")
    assert r.status_code == 200
    body = r.text
    assert 'class="sidebar"' in body
    assert 'class="page-h1">History</h1>' in body
    assert 'class="data-table' in body or 'class="empty-state"' in body
    assert "<style>" not in body
