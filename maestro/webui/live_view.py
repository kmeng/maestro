"""Web UI live execution-flow view (T3.8, Epic 3).

Renders a skeleton page that subscribes to the dispatch-log SSE stream
via the browser's native EventSource API. Two zones (Running /
Completed) update on the client based on event_type. Chinese labels per
D6 cross-cutting language rule.

Server side is just the skeleton render — all reactivity is in the
inline JS in live.html. SSE handled by /api/dispatch_log/stream (T3.6).
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/live", response_class=HTMLResponse)
async def live_view(request: Request) -> HTMLResponse:
    from maestro.webui import templates  # late-bind: avoids name collision with templates/ subdir during pytest collection
    return templates.TemplateResponse(request, "live.html", {})
