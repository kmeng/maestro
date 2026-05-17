from fastapi.testclient import TestClient
from maestro.webui import app


def test_savings_extends_base():
    client = TestClient(app)
    r = client.get("/savings")
    assert r.status_code == 200
    body = r.text
    assert 'class="sidebar"' in body
    assert 'class="page-h1">成本节省</h1>' in body
    assert ('class="kpis"' in body) or ('class="empty-state"' in body)
    assert "<style>" not in body
