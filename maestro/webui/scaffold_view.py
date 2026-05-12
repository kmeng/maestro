"""Web UI screens for project scaffolding (T2.7).

Server-rendered Jinja2 templates with htmx interactivity (ADR-0002:
no JS bundle, no build). Routes compose the same upstream functions
as ``scaffold_api`` (T2.6) but render HTML instead of JSON / SSE.

Routes:
- ``GET /scaffold``                       — project picker form
- ``GET /scaffold/plan?path&mode``        — 3-layer disclosure plan preview
- ``GET /scaffold/plan-row/{path}?...``   — drill-down partial (htmx target)
- ``POST /scaffold/apply``                — execute apply, render final state

v0.0.3 limitation: ``/scaffold/apply`` is synchronous (waits for all
apply events then renders a final-state page). Full live SSE updates
in the browser deferred to v0.0.4 — the underlying T2.6 SSE endpoint
remains exposed for external clients.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from maestro.scaffold.engine import generate_plan
from maestro.scaffold.io import (
    FileFailed,
    FileStarted,
    FileSucceeded,
    PlanComplete,
    apply_plan,
    read_bytes,
)
from maestro.scaffold.operations import Operation, PlanRow
from maestro.scaffold.preflight import run_preflight
from maestro.webui.scaffold_api import _build_filespecs, _read_existing
from maestro.registry.projects import upsert_project

router = APIRouter()


# Chinese labels for ops — used by template via the `op_label` callable.
_OP_LABELS: dict[str, str] = {
    "CREATE": "创建",
    "APPEND_DELIMITED": "追加",
    "NOOP": "无需修改",
    "CONFLICT": "冲突",
}


_CONFLICT_REASON_CHINESE: dict[str, str] = {
    "replacement_differs": "文件已存在且内容与 Maestro 模板不同——可能是您的自定义版本",
    "delimiter_body_differs": "您手动修改过 Maestro 区段内容",
    "delimiter_version_mismatch": "Maestro 区段版本不匹配（可能是旧版 Maestro 创建）",
    "multiple_delimiter_blocks": "文件中存在多个 Maestro 起始标记（已损坏）",
    "unclosed_delimiter": "Maestro 区段未正确闭合（已损坏）",
}


Mode = Literal["new_project", "take_over"]


def _validate_mode(mode: str) -> Mode:
    """Validate mode literal. Raises HTTPException(400) on invalid."""
    if mode not in ("new_project", "take_over"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    return mode  # type: ignore[return-value]


def _compose_plan(project_root: Path, mode: Mode):
    """Return (preflight_tuple, files_list, plan) — the same composition
    scaffold_api.py uses for its /api/scaffold/plan endpoint.

    Kept as a private helper here (vs importing from scaffold_api) so the
    view layer can also access the raw FileSpec list for drill-down
    rendering, which the JSON API doesn't need.
    """
    preflight = run_preflight(project_root, mode)
    files = _build_filespecs(mode)
    existing = _read_existing(project_root, files)
    plan = generate_plan(files, existing)
    return preflight, files, plan


def _row_to_dict(row: PlanRow) -> dict:
    """Convert PlanRow dataclass to a template-friendly dict (resolves
    enum to its string value)."""
    return {
        "path": row.path,
        "op": row.op.value,
        "detail": row.detail,
        "conflict_reason": row.conflict_reason.value if row.conflict_reason else None,
    }


def _events_to_dicts(events: Iterable) -> list[dict]:
    """Convert the dataclass events from apply_plan into dicts the
    template iterates over. PlanComplete intentionally omitted from this
    list (it's reported separately via aggregate counters)."""
    out = []
    for ev in events:
        if isinstance(ev, FileStarted):
            out.append({"type": "file_started", "path": ev.path})
        elif isinstance(ev, FileSucceeded):
            out.append({"type": "file_succeeded", "path": ev.path, "op": ev.op.value})
        elif isinstance(ev, FileFailed):
            out.append({"type": "file_failed", "path": ev.path, "error": ev.error})
        # PlanComplete handled by caller via counters.
    return out


# -- Routes -----------------------------------------------------------------

@router.get("/scaffold", response_class=HTMLResponse)
async def picker(request: Request):
    """Render the project picker form."""
    # Late import to avoid circular: webui/__init__.py imports scaffold_view.
    from maestro.webui import templates
    return templates.TemplateResponse(request, "scaffold_picker.html", {})


@router.get("/scaffold/plan", response_class=HTMLResponse)
async def plan_page(
    request: Request, path: str = Query(...), mode: str = Query(...)
):
    """Render the 3-layer disclosure plan preview.

    Apply button is disabled when ANY preflight check fails OR ANY plan
    row is CONFLICT (all v0.0.3 files are "required" per design 14 D3;
    no optional-file CONFLICT case to differentiate).
    """
    from maestro.webui import templates
    validated_mode = _validate_mode(mode)
    project_root = Path(path).resolve()
    preflight, _files, plan = _compose_plan(project_root, validated_mode)

    rows_dict = [_row_to_dict(r) for r in plan.rows]
    preflight_dict = [
        {"name": c.name, "passed": c.passed, "message": c.message}
        for c in preflight
    ]
    all_preflight_pass = all(c.passed for c in preflight)
    has_required_conflict = any(r.op == Operation.CONFLICT for r in plan.rows)

    return templates.TemplateResponse(
        request,
        "scaffold_plan.html",
        {
            "path": str(project_root),
            "mode": validated_mode,
            "preflight": preflight_dict,
            "rows": rows_dict,
            "all_preflight_pass": all_preflight_pass,
            "has_required_conflict": has_required_conflict,
            "op_label": lambda op: _OP_LABELS.get(op, op),
        },
    )


@router.get("/scaffold/plan-row/{row_path:path}", response_class=HTMLResponse)
async def plan_row_partial(
    request: Request,
    row_path: str,
    path: str = Query(...),
    mode: str = Query(...),
):
    """Drill-down partial for a single plan row.

    Re-generates the plan to find the matching row — keeps the view
    stateless (no session needed). The generate_plan call is pure +
    fast; cost is acceptable for a click-to-expand UX.
    """
    from maestro.webui import templates
    validated_mode = _validate_mode(mode)
    project_root = Path(path).resolve()
    _preflight, files, plan = _compose_plan(project_root, validated_mode)

    row = next((r for r in plan.rows if r.path == row_path), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")

    context = {
        "row": _row_to_dict(row),
        "path": str(project_root),
        "mode": validated_mode,
    }

    if row.op == Operation.APPEND_DELIMITED:
        # Read the actual existing file content for the diff preview.
        # Find the matching FileSpec to get the wrapped section we'd append.
        spec = next((f for f in files if f.path == row_path), None)
        existing_path = project_root / row_path
        existing_text = ""
        try:
            existing_bytes = read_bytes(existing_path)
            if existing_bytes:
                # Truncate to 500 chars to keep the page bounded.
                existing_text = existing_bytes.decode("utf-8", errors="replace")[:500]
        except OSError:
            pass
        context["existing_content"] = existing_text
        # Render the same wrapped section apply_plan would write.
        if spec is not None and hasattr(spec, "section_body"):
            version = spec.section_version
            body = spec.section_body.strip(b"\n").decode("utf-8", errors="replace")
            context["wrapped_section"] = (
                f"<!-- maestro:start v={version} -->\n"
                f"{body}\n"
                f"<!-- maestro:end v={version} -->\n"
            )
        else:
            context["wrapped_section"] = ""
    elif row.op == Operation.CONFLICT:
        reason = row.conflict_reason.value if row.conflict_reason else ""
        context["conflict_reason_chinese"] = _CONFLICT_REASON_CHINESE.get(
            reason, "未知冲突原因"
        )

    return templates.TemplateResponse(
        request, "scaffold_plan_row.html", context
    )


@router.post("/scaffold/apply", response_class=HTMLResponse)
async def apply_submit(request: Request):
    """Execute the apply and render the final-state page.

    v0.0.3 implements this as a synchronous collect-then-render flow
    (the user sees the result page after all events arrive). The
    underlying T2.6 SSE endpoint remains exposed for clients that want
    live updates; the in-browser live-update view is deferred to v0.0.4.

    Mirrors scaffold_api.scaffold_apply's logic:
    - Preflight fail → render rejection page; no upsert.
    - Else: filter files by accepted_paths, run apply_plan, collect
      events, register project (only if plan.rows non-empty per T2.6 fix).
    """
    from maestro.webui import templates
    form = await request.form()
    path = form.get("path")
    mode = form.get("mode")
    accepted_paths = form.getlist("accepted_paths")

    if not path or not mode:
        raise HTTPException(status_code=400, detail="Missing path or mode")
    validated_mode = _validate_mode(mode)
    project_root = Path(path).resolve()

    # Re-run preflight server-side — even though the plan page disabled
    # the button on failing checks, the user could craft the POST
    # directly. Defense in depth.
    preflight = run_preflight(project_root, validated_mode)
    failed_checks = [c for c in preflight if not c.passed]
    if failed_checks:
        return templates.TemplateResponse(
            request,
            "scaffold_apply.html",
            {
                "rejected": True,
                "rejected_checks": [
                    {"name": c.name, "message": c.message} for c in failed_checks
                ],
                "events": [],
                "succeeded": 0,
                "failed": 0,
            },
        )

    all_files = _build_filespecs(validated_mode)
    files = [f for f in all_files if f.path in accepted_paths]
    existing = _read_existing(project_root, files)
    plan = generate_plan(files, existing)

    events = []
    succeeded = 0
    failed = 0
    for ev in apply_plan(plan, files, project_root):
        if isinstance(ev, PlanComplete):
            succeeded = ev.succeeded
            failed = ev.failed
        else:
            events.append(ev)

    # Same skip-upsert-on-empty-plan guard as scaffold_api (T2.6 fix).
    if plan.rows:
        upsert_project(project_root)

    return templates.TemplateResponse(
        request,
        "scaffold_apply.html",
        {
            "rejected": False,
            "rejected_checks": [],
            "events": _events_to_dicts(events),
            "succeeded": succeeded,
            "failed": failed,
        },
    )
