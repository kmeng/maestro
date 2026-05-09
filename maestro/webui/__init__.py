"""Web UI HTTP server entry point.

Exposes:
- GET /health  – liveness probe for ops
- GET /version – returns the running version string

Page rendering, launcher, htmx, and port-conflict handling are out of scope (T0.4 / T0.5).
"""

from fastapi import FastAPI

import maestro

app = FastAPI(title="Maestro Web UI", version=maestro.__version__)


@app.get("/health")
async def health():
    """Liveness probe for ops."""
    return {"status": "ok"}


@app.get("/version")
async def version():
    """Lets the UI display the running version."""
    return {"version": maestro.__version__}
