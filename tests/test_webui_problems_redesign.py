from fastapi.testclient import TestClient
from maestro.webui import app


def test_problems_extends_base_empty_state():
    client = TestClient(app)
    r = client.get("/problems")
    assert r.status_code == 200
    body = r.text
    assert 'class="sidebar"' in body
    assert 'class="page-h1">Problems</h1>' in body
    assert 'class="empty-state"' in body or 'class="problem-row' in body
    assert "ackRow" in body
