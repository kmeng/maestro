from fastapi.testclient import TestClient
from maestro.webui import app


def test_scaffold_picker_extends_base():
    client = TestClient(app)
    r = client.get("/scaffold")
    assert r.status_code == 200
    body = r.text
    assert 'class="sidebar"' in body
    assert 'class="page-h1">Scaffold</h1>' in body
    assert 'name="path"' in body
    assert 'name="mode"' in body
    assert "<style>" not in body  # no inline page-level style block in picker
