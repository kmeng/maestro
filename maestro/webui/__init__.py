"""Web UI HTTP server entry point.

Exposes:
- GET /        – hero page rendered via Jinja2 template
- GET /health  – liveness probe for ops
- GET /version – returns the running version string
- /api/team    – team.yaml read/write API (T1.3)
- /wizard      – team-composition wizard (T1.4)
- /team        – team config standing view + per-row edit (T1.5)
- /static/*    – serves vendored static assets (htmx, future CSS/JS)

Launcher and port-conflict handling are out of scope (T0.5).
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import maestro
from maestro.scaffold import io as _scaffold_io  # noqa: F401  # T2.2 startup wiring
from maestro.webui.team_api import router as team_router
from maestro.webui.team_catalog import router as team_catalog_router
from maestro.webui.wizard import router as wizard_router

app = FastAPI(title="Maestro Web UI", version=maestro.__version__)
app.include_router(team_router)
app.include_router(wizard_router)
app.include_router(team_catalog_router)

_STATIC_DIR = Path(__file__).parent / "static"
_TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Vendored htmx + future static assets; no CDN at runtime per ADR-0002
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the hero page with running version."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"version": maestro.__version__},
    )


@app.get("/health")
async def health():
    """Liveness probe for ops."""
    return {"status": "ok"}


@app.get("/version")
async def version():
    """Lets the UI display the running version."""
    return {"version": maestro.__version__}
