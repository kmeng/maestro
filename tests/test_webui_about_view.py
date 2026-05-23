from fastapi.testclient import TestClient
from maestro.webui import app

client = TestClient(app)


def test_about_page_renders():
    r = client.get("/about")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_about_page_has_slogan_and_intro():
    body = client.get("/about").text
    assert "你来指挥，AI 来演奏" in body
    assert "用初级的价，拿资深的活" in body


def test_about_page_has_both_qr_codes():
    body = client.get("/about").text
    assert "/static/qr-wechat-mp.jpg" in body
    assert "/static/qr-wechat-personal.jpg" in body
    assert body.count("挖宝的瓦力") >= 2


def test_about_page_has_github_link():
    body = client.get("/about").text
    assert "https://github.com/kmeng/maestro/issues" in body


def test_about_nav_active():
    import re
    body = client.get("/about").text
    active = re.findall(r'<a[^>]*aria-current="page"[^>]*>', body)
    assert len(active) == 1
    assert 'href="/about"' in active[0]
