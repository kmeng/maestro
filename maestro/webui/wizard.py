"""Wizard endpoints for the first-launch team-composition UI (T1.4)."""

import maestro
from fastapi import APIRouter, Form, Request
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
from maestro.webui import team_api


def _templates():
    """Deferred import to avoid circular dependency with webui.__init__."""
    from maestro.webui import templates

    return templates


router = APIRouter(prefix="/wizard", tags=["wizard"])

_DEFAULT_ALIAS = {
    "coder": "Cody",
    "librarian": "Lily",
    "reviewer": "Rae",
    "scribe": "Sage",
}

ROLE_ORDER = ["coder", "librarian", "reviewer", "scribe"]
ROLE_TITLES = {
    "coder": "编码员 / Coder",
    "librarian": "图书管理员 / Librarian",
    "reviewer": "审阅员 / Reviewer",
    "scribe": "记录员 / Scribe",
}

_ERROR_MESSAGES = {
    "String should have at least 1 character": "不能为空",
    "must not be empty": "不能为空",
    "String should have at most 64 characters": "长度不超过 64 个字符",
    "must be at most 64 characters": "长度不超过 64 个字符",
    "String should have at most 128 characters": "长度不超过 128 个字符",
    "must be at most 128 characters": "长度不超过 128 个字符",
    "must not contain control characters": "不能包含控制字符（例如换行、制表符）",
    "String should match pattern": "格式应为小写字母数字加点/横线/下划线（首字符必须是字母或数字）",
    "must match pattern": "格式应为小写字母数字加点/横线/下划线（首字符必须是字母或数字）",
    "is used by multiple roles": "成员名与其他角色重复",
}


def translate_error(msg: str) -> str:
    """Map a Pydantic error message to Chinese; fall back to raw English."""
    for key, chinese in _ERROR_MESSAGES.items():
        if key in msg:
            return chinese
    return msg


def _existing_or_default(role: str, field: str) -> str:
    """Return the existing team.yaml value for (role, field) or a sensible default."""
    config = load_team_config(team_api._project_root())

    if isinstance(config, TeamConfig):
        entry = config.roles.get(role)
        if entry is not None:
            return entry.member if field == "member" else entry.model

    # Absent or invalid → use defaults
    if field == "member":
        return _DEFAULT_ALIAS[role]
    return DEFAULT_MODELS[role]


@router.get("", response_class=HTMLResponse)
async def wizard_start(request: Request):
    """Render the wizard shell with step1 inside."""
    templates = _templates()
    step_html = templates.get_template("wizard_step1.html").render()
    return templates.TemplateResponse(
        request,
        "wizard.html",
        {"step_html": step_html, "version": maestro.__version__},
    )


@router.post("/step2-back", response_class=HTMLResponse)
async def wizard_step2_back():
    """Go back to step1."""
    templates = _templates()
    step1 = templates.get_template("wizard_step1.html").render()
    return HTMLResponse(content=step1)


@router.post("/step2", response_class=HTMLResponse)
async def wizard_step2():
    """Render the role details form with pre-filled values."""
    values = {
        role: {
            "member": _existing_or_default(role, "member"),
            "model": _existing_or_default(role, "model"),
        }
        for role in ROLE_ORDER
    }

    templates = _templates()
    html = templates.get_template("wizard_step2.html").render(
        values=values,
        field_errors={},
        top_error="",
        role_order=ROLE_ORDER,
        role_titles=ROLE_TITLES,
    )
    return HTMLResponse(content=html)


@router.post("/validate-field", response_class=HTMLResponse)
async def validate_field(
    role: str = Form(...),
    field: str = Form(...),
    value: str = Form(...),
):
    """Single-field server-side validation, returns error span or empty."""
    if role not in ROLE_IDS:
        # Use the same template path so all responses are consistent.
        templates = _templates()
        html = templates.get_template("wizard_field_error.html").render(message="")
        return HTMLResponse(content=html)

    # Pair the value under test with a known-good sibling so single-field
    # validation doesn't trip on the unfilled other field.
    if field == "member":
        member, model = value, DEFAULT_MODELS[role]
    else:
        member, model = _DEFAULT_ALIAS[role], value

    try:
        RoleEntry(member=member, model=model)
    except ValidationError as exc:
        message = ""
        for err in exc.errors():
            loc = err.get("loc", ())
            if field in loc:
                message = translate_error(err.get("msg", ""))
                break
        if not message and exc.errors():
            message = translate_error(exc.errors()[0].get("msg", ""))
        templates = _templates()
        html = templates.get_template("wizard_field_error.html").render(message=message)
        return HTMLResponse(content=html)

    # Validation passed — empty span placeholder.
    templates = _templates()
    html = templates.get_template("wizard_field_error.html").render(message="")
    return HTMLResponse(content=html)


def _form_to_values(form_data: dict) -> dict:
    """Collect the 8 form fields into role-keyed dict."""
    return {
        role: {
            "member": form_data.get(f"member_{role}", ""),
            "model": form_data.get(f"model_{role}", ""),
        }
        for role in ROLE_ORDER
    }


def _team_config_errors(values: dict) -> tuple[dict, str]:
    """Validate the values dict against TeamConfig. Return (field_errors, top_error)."""
    field_errors: dict = {}
    top_error = ""
    try:
        TeamConfig.model_validate({"schema_version": 1, "roles": values})
    except ValidationError as exc:
        for err in exc.errors():
            loc = err.get("loc", ())
            msg = translate_error(err.get("msg", ""))
            # Common shapes: ('roles',), ('roles', 'coder', 'member'), ()
            if len(loc) >= 3 and loc[0] == "roles":
                role, field = loc[1], loc[2]
                field_errors[(role, field)] = msg
            else:
                top_error = msg
    return field_errors, top_error


@router.post("/step3", response_class=HTMLResponse)
async def wizard_step3(
    member_coder: str = Form(""),
    model_coder: str = Form(""),
    member_librarian: str = Form(""),
    model_librarian: str = Form(""),
    member_reviewer: str = Form(""),
    model_reviewer: str = Form(""),
    member_scribe: str = Form(""),
    model_scribe: str = Form(""),
):
    """Validate full form. On success render summary; else re-render step2 with errors."""
    values = _form_to_values(locals())

    field_errors, top_error = _team_config_errors(values)
    if field_errors or top_error:
        templates = _templates()
        html = templates.get_template("wizard_step2.html").render(
            values=values,
            field_errors=field_errors,
            top_error=top_error,
            role_order=ROLE_ORDER,
            role_titles=ROLE_TITLES,
        )
        return HTMLResponse(content=html)

    templates = _templates()
    html = templates.get_template("wizard_step3.html").render(
        values=values, role_order=ROLE_ORDER, role_titles=ROLE_TITLES
    )
    return HTMLResponse(content=html)


@router.post("/save", response_class=HTMLResponse)
async def wizard_save(
    member_coder: str = Form(""),
    model_coder: str = Form(""),
    member_librarian: str = Form(""),
    model_librarian: str = Form(""),
    member_reviewer: str = Form(""),
    model_reviewer: str = Form(""),
    member_scribe: str = Form(""),
    model_scribe: str = Form(""),
):
    """Persist the team config and render the 'done' page."""
    values = _form_to_values(locals())

    field_errors, top_error = _team_config_errors(values)
    if field_errors or top_error:
        # Defensive — step3 should have caught this. Re-render step2 with errors.
        templates = _templates()
        html = templates.get_template("wizard_step2.html").render(
            values=values,
            field_errors=field_errors,
            top_error=top_error,
            role_order=ROLE_ORDER,
            role_titles=ROLE_TITLES,
        )
        return HTMLResponse(content=html)

    config = TeamConfig.model_validate({"schema_version": 1, "roles": values})
    try:
        save_team_config(team_api._project_root(), config)
    except OSError as exc:
        templates = _templates()
        html = templates.get_template("wizard_step4.html").render(
            success=False, error_msg=f"保存失败：{exc}"
        )
        return HTMLResponse(content=html)

    templates = _templates()
    html = templates.get_template("wizard_step4.html").render(success=True, error_msg="")
    return HTMLResponse(content=html)
