"""Team catalog standing view (read + per-row edit) — T1.5."""

import maestro
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from maestro.team import (
    DEFAULT_MODELS,
    ROLE_IDS,
    RoleEntry,
    TeamConfig,
    TeamConfigInvalid,
    load_team_config,
    save_team_config,
)
from maestro.webui import team_api  # module reference so monkeypatch on team_api._project_root works


def _templates():
    """Defer the templates import to avoid circular imports at module load."""
    from maestro.webui import templates

    return templates


router = APIRouter(prefix="/team", tags=["team_catalog"])

ROLE_ORDER = ["coder", "librarian", "reviewer", "scribe"]
ROLE_TITLES = {
    "coder": "编码员 / Coder",
    "librarian": "图书管理员 / Librarian",
    "reviewer": "审阅员 / Reviewer",
    "scribe": "记录员 / Scribe",
}

_ERROR_MESSAGES = {
    "must not be empty": "不能为空",
    "must be at most 64 characters": "长度不超过 64 个字符",
    "must be at most 128 characters": "长度不超过 128 个字符",
    "must not contain control characters": "不能包含控制字符",
    "must match pattern": "格式应为小写字母数字加点/横线/下划线",
    "is used by multiple roles": "成员名与其他角色重复",
}


def translate_error(msg: str) -> str:
    for key, chinese in _ERROR_MESSAGES.items():
        if key in msg:
            return chinese
    return msg


@router.get("", response_class=HTMLResponse)
async def get_team_catalog(request: Request):
    result = load_team_config(team_api._project_root())

    context = {
        "request": request,
        "version": maestro.__version__,
        "role_order": ROLE_ORDER,
        "role_titles": ROLE_TITLES,
        "missing": False,
        "invalid": False,
        "invalid_reason": "",
    }

    if result is None:
        context["missing"] = True
    elif isinstance(result, TeamConfigInvalid):
        context["invalid"] = True
        context["invalid_reason"] = result.reason
    else:
        rows = {}
        for role in ROLE_ORDER:
            entry = result.roles[role]
            rows[role] = {"member": entry.member, "model": entry.model}
        context["rows"] = rows

    templates = _templates()
    return templates.TemplateResponse(request, "team_catalog.html", context)


@router.get("/edit/{role}", response_class=HTMLResponse)
async def get_edit_row(role: str):
    if role not in ROLE_IDS:
        raise HTTPException(404, "unknown role")

    result = load_team_config(team_api._project_root())
    if result is None or isinstance(result, TeamConfigInvalid):
        raise HTTPException(400, "team.yaml not in a valid state for row edit")

    entry = result.roles[role]
    templates = _templates()
    html = templates.get_template("team_catalog_row.html").render(
        role=role,
        role_titles=ROLE_TITLES,
        entry={"member": entry.member, "model": entry.model},
        mode="edit",
        field_errors={},
    )
    return HTMLResponse(content=html)


@router.post("/edit/{role}", response_class=HTMLResponse)
async def post_edit_row(
    role: str,
    member: str = Form(...),
    model: str = Form(...),
):
    if role not in ROLE_IDS:
        raise HTTPException(404, "unknown role")

    existing = load_team_config(team_api._project_root())
    if existing is None or isinstance(existing, TeamConfigInvalid):
        raise HTTPException(400, "team.yaml not in a valid state for row edit")

    # Build new config with this row replaced
    payload_roles = {}
    for r in ROLE_ORDER:
        if r == role:
            payload_roles[r] = {"member": member, "model": model}
        else:
            entry = existing.roles[r]
            payload_roles[r] = {"member": entry.member, "model": entry.model}

    try:
        new_config = TeamConfig(schema_version=1, roles=payload_roles)
    except ValidationError as exc:
        field_errors = {}
        for err in exc.errors():
            loc = err.get("loc", ())
            msg = translate_error(err.get("msg", ""))
            if len(loc) >= 2 and loc[0] == "roles" and loc[1] == role and len(loc) >= 3:
                field_errors[loc[2]] = msg
            elif "is used by multiple roles" in err.get("msg", ""):
                field_errors["member"] = msg
        templates = _templates()
        html = templates.get_template("team_catalog_row.html").render(
            role=role,
            role_titles=ROLE_TITLES,
            entry={"member": member, "model": model},
            mode="edit",
            field_errors=field_errors,
        )
        return HTMLResponse(content=html)

    save_team_config(team_api._project_root(), new_config)
    saved = load_team_config(team_api._project_root())
    saved_entry = saved.roles[role]

    templates = _templates()
    html = templates.get_template("team_catalog_row.html").render(
        role=role,
        role_titles=ROLE_TITLES,
        entry={"member": saved_entry.member, "model": saved_entry.model},
        mode="view",
        field_errors={},
    )
    return HTMLResponse(content=html)


@router.get("/row/{role}", response_class=HTMLResponse)
async def get_view_row(role: str):
    if role not in ROLE_IDS:
        raise HTTPException(404, "unknown role")

    result = load_team_config(team_api._project_root())
    if result is None or isinstance(result, TeamConfigInvalid):
        raise HTTPException(400, "team.yaml not in a valid state for row edit")

    entry = result.roles[role]
    templates = _templates()
    html = templates.get_template("team_catalog_row.html").render(
        role=role,
        role_titles=ROLE_TITLES,
        entry={"member": entry.member, "model": entry.model},
        mode="view",
        field_errors={},
    )
    return HTMLResponse(content=html)
