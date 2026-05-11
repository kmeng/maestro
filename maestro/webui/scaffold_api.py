"""HTTP API for project scaffolding (T2.6).

Two endpoints:

- ``POST /api/scaffold/plan`` — returns the pre-flight + plan-row JSON
  for a chosen project root + mode. Status always 200 (preflight
  failures are part of the response body, not HTTP errors); pure
  upstream APIs guarantee no internal exceptions.

- ``POST /api/scaffold/apply`` — streams per-file apply events via SSE
  (sse-starlette). On any failing preflight check, emits a single
  ``plan_rejected`` event and closes — never runs apply. Otherwise
  runs ``apply_plan`` and emits ``file_started`` / ``file_succeeded``
  / ``file_failed`` / ``plan_complete``. After ``plan_complete``,
  registers the project via ``upsert_project`` (which **NEVER raises**
  per T2.5's bulletproof outer try/except — see
  ``maestro/registry/projects.py`` module docstring).

Design choices documented inline:
- Sync generator into ``EventSourceResponse``: ``apply_plan`` is a
  sync generator and sse-starlette accepts both. Wrapping in
  ``asyncio.to_thread`` would buy nothing for this CPU/IO mix.
- ``plan_rejected`` on the SSE stream (vs HTTP 4xx): keeps the
  client's parser uniform — it already knows how to consume SSE.
- No try/except around ``upsert_project``: T2.5 contract guarantees
  it never raises; wrapping would be dead code.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from maestro.scaffold.engine import generate_plan
from maestro.scaffold.io import (
    FileFailed,
    FileStarted,
    FileSucceeded,
    PlanComplete,
    apply_plan,
    read_bytes,
)
from maestro.scaffold.operations import (
    FileSpec,
    MergeableFile,
    Plan,
    ReplacementFile,
)
from maestro.scaffold.preflight import run_preflight
from maestro.scaffold.templates import (
    render_claude_md_section_body,
    render_claude_md_standalone,
    render_gitignore,
    render_maestro_gitignore,
    render_readme_stub,
)
from maestro.registry.projects import upsert_project

router = APIRouter(prefix="/api/scaffold", tags=["scaffold"])


# -- Request / response models ----------------------------------------------

class PlanRequest(BaseModel):
    path: str
    mode: Literal["new_project", "take_over"]


class ApplyRequest(BaseModel):
    path: str
    mode: Literal["new_project", "take_over"]
    accepted_paths: list[str]


class PreflightCheckResponse(BaseModel):
    name: str
    passed: bool
    message: str


class PlanRowResponse(BaseModel):
    path: str
    op: str
    detail: str
    conflict_reason: str | None = None


class PlanResponse(BaseModel):
    preflight: list[PreflightCheckResponse]
    rows: list[PlanRowResponse]


# -- Internal helpers -------------------------------------------------------

def _build_filespecs(mode: Literal["new_project", "take_over"]) -> list[FileSpec]:
    """Construct the ordered FileSpec list for the chosen mode per ADR-0005."""
    if mode == "take_over":
        return [
            ReplacementFile(
                path=".maestro/.gitignore", rendered=render_maestro_gitignore()
            ),
            MergeableFile(
                path="CLAUDE.md",
                section_body=render_claude_md_section_body(),
                standalone_full=render_claude_md_standalone(),
                section_version=1,
            ),
        ]
    # new_project
    return [
        ReplacementFile(path=".gitignore", rendered=render_gitignore()),
        ReplacementFile(path="README.md", rendered=render_readme_stub()),
        MergeableFile(
            path="CLAUDE.md",
            section_body=render_claude_md_section_body(),
            standalone_full=render_claude_md_standalone(),
            section_version=1,
        ),
        ReplacementFile(
            path=".maestro/.gitignore", rendered=render_maestro_gitignore()
        ),
    ]


def _read_existing(project_root: Path, files: list[FileSpec]) -> dict[str, bytes | None]:
    """Snapshot the on-disk bytes for each FileSpec's path. OSError → None."""
    existing: dict[str, bytes | None] = {}
    for spec in files:
        try:
            existing[spec.path] = read_bytes(project_root / spec.path)
        except OSError:
            existing[spec.path] = None
    return existing


# -- Endpoints --------------------------------------------------------------

@router.post("/plan", response_model=PlanResponse)
def scaffold_plan(req: PlanRequest) -> PlanResponse:
    """Return preflight + plan rows. Status always 200."""
    project_root = Path(req.path).resolve()
    preflight_checks = run_preflight(project_root, req.mode)
    files = _build_filespecs(req.mode)
    existing = _read_existing(project_root, files)
    plan: Plan = generate_plan(files, existing)

    return PlanResponse(
        preflight=[
            PreflightCheckResponse(name=c.name, passed=c.passed, message=c.message)
            for c in preflight_checks
        ],
        rows=[
            PlanRowResponse(
                path=r.path,
                op=r.op.value,
                detail=r.detail,
                conflict_reason=r.conflict_reason.value if r.conflict_reason else None,
            )
            for r in plan.rows
        ],
    )


@router.post("/apply")
async def scaffold_apply(req: ApplyRequest) -> EventSourceResponse:
    """Stream per-file apply events via SSE.

    On any failing preflight check, emits a single ``plan_rejected``
    event and closes (no apply, no upsert). Otherwise streams
    ``apply_plan`` events and registers the project at end.
    """
    project_root = Path(req.path).resolve()
    preflight_checks = run_preflight(project_root, req.mode)

    failed_checks = [c for c in preflight_checks if not c.passed]
    if failed_checks:
        # Plan rejected — single event, no apply, no upsert.
        def reject_gen():
            yield {
                "event": "plan_rejected",
                "data": json.dumps({
                    "reason": "preflight_failed",
                    "checks": [
                        {"name": c.name, "passed": c.passed, "message": c.message}
                        for c in failed_checks
                    ],
                }),
            }
        return EventSourceResponse(reject_gen())

    all_files = _build_filespecs(req.mode)
    files = [f for f in all_files if f.path in req.accepted_paths]
    existing = _read_existing(project_root, files)
    plan = generate_plan(files, existing)

    def event_generator():
        for event in apply_plan(plan, files, project_root):
            if isinstance(event, FileStarted):
                yield {
                    "event": "file_started",
                    "data": json.dumps({"path": event.path}),
                }
            elif isinstance(event, FileSucceeded):
                yield {
                    "event": "file_succeeded",
                    "data": json.dumps({"path": event.path, "op": event.op.value}),
                }
            elif isinstance(event, FileFailed):
                yield {
                    "event": "file_failed",
                    "data": json.dumps({"path": event.path, "error": event.error}),
                }
            elif isinstance(event, PlanComplete):
                yield {
                    "event": "plan_complete",
                    "data": json.dumps({
                        "succeeded": event.succeeded,
                        "failed": event.failed,
                    }),
                }
        # T2.5 contract: upsert_project NEVER raises. No try/except needed.
        upsert_project(project_root)

    return EventSourceResponse(event_generator())
