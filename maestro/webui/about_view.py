from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    from maestro.webui import templates  # lazy import to avoid collision with templates subdirectory
    return templates.TemplateResponse(request, "about.html", {})
