import jinja2
from pathlib import Path
import re

import maestro
from fastapi.testclient import TestClient

from maestro.webui import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE_PATH = PROJECT_ROOT / "maestro" / "webui" / "templates" / "_base.html"


def _render_child(context: dict) -> str:
    base_content = BASE_TEMPLATE_PATH.read_text(encoding="utf-8")
    env = jinja2.Environment(
        loader=jinja2.DictLoader({
            "_base.html": base_content,
            "child.html": '{% extends "_base.html" %}'
                          '{% block content %}hi{% endblock %}'
                          '{% block title %}TestPage{% endblock %}',
        }),
        autoescape=True,
    )
    template = env.get_template("child.html")
    return template.render(context)


def test_base_template_renders_with_minimal_child():
    html = _render_child({"version": "0.0.4"})

    assert "<title>Maestro · TestPage</title>" in html
    assert '<link rel="stylesheet" href="/static/maestro.css">' in html

    # content inside main
    assert '<main class="main">' in html
    assert "hi" in html  # block content present

    # all nav links
    for href in [
        "/",
        "/team",
        "/scaffold",
        "/live",
        "/history",
        "/savings",
        "/problems",
    ]:
        assert f'href="{href}"' in html

    # version in brand-sub
    assert "v0.0.4" in html


def test_base_template_marks_active_nav():
    html = _render_child({"version": "0.0.4", "nav_active": "team"})

    # Find <a> tags carrying aria-current="page" (order-agnostic re. href/class)
    active_tags = re.findall(r'<a[^>]*aria-current="page"[^>]*>', html)
    assert len(active_tags) == 1, f"Expected exactly 1 active link, got {len(active_tags)}: {active_tags}"
    assert 'href="/team"' in active_tags[0]
    assert 'class="active"' in active_tags[0]


def test_version_shown_on_non_index_pages():
    client = TestClient(app)
    # /scaffold is a non-index page that extends _base.html
    body = client.get("/scaffold").text
    assert f"v{maestro.__version__}" in body
