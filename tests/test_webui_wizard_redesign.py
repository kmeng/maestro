from fastapi.testclient import TestClient
from maestro.webui import app


def test_wizard_shell_extends_base():
    client = TestClient(app)
    r = client.get("/wizard")
    assert r.status_code == 200
    body = r.text
    # Base
    assert 'class="sidebar"' in body
    assert 'class="page-h1">Team setup wizard</h1>' in body
    # Step 1 inside the shell
    assert 'data-step="1"' in body
    assert "下一步" in body
    # wizard-progress markup
    assert 'class="wizard-progress"' in body
    # Page-specific <style> for progress dots
    assert ".wp-dot" in body
