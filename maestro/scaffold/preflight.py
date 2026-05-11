"""Pre-flight checks for the scaffolding flows (T2.3).

Per ADR-0006 § Pre-flight, these 4 checks gate plan application:

1. ``directory_exists`` — the path the user pointed at exists and is
   a directory.
2. ``git_state`` — git state matches the chosen flow (take_over needs
   ``.git/``; new_project needs an empty directory).
3. ``clean_tree`` (take_over only) — ``git status --porcelain`` is
   empty; refuses on dirty trees rather than risk writing atop
   in-progress edits.
4. ``no_existing_maestro`` (take_over only) — ``.maestro/`` contains
   nothing beyond ``.maestro/.gitignore`` (the take-over set per
   ADR-0005).

Returns are :class:`PreflightCheck` records; the UI (T2.7) renders
passing checks as a ✓ summary and failing checks prominently above
the plan rows.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from .operations import PreflightCheck

Flow = Literal["new_project", "take_over"]

# Per ADR-0005 take-over set: `.maestro/.gitignore` is the only file
# Maestro writes under `.maestro/`. Anything else inside `.maestro/`
# (e.g. `team.yaml` from the wizard, `logs/`, third-party config)
# indicates a prior take-over or a hand-built setup — we surface it
# rather than silently overwrite.
_TAKE_OVER_MAESTRO_FILES = {".gitignore"}

# 10s is generous for `git status --porcelain` even on huge repos;
# ensures we never hang the wizard on a stuck git operation.
_GIT_TIMEOUT_SECONDS = 10


def check_directory_exists(project_root: Path) -> PreflightCheck:
    """Check 1: the path the user pointed at exists and is a directory."""
    if project_root.is_dir():
        return PreflightCheck(
            name="directory_exists", passed=True, message="目录存在"
        )
    # is_dir() returns False for both "doesn't exist" and "is a file" —
    # we collapse both into one user message because the user's fix is
    # the same either way (pick a different path).
    return PreflightCheck(
        name="directory_exists",
        passed=False,
        message=f"目录不存在: {project_root}",
    )


def check_git_state(project_root: Path, flow: Flow) -> PreflightCheck:
    """Check 2: git state matches the flow.

    take_over: ``.git/`` must exist as a directory.
    new_project: the directory must be empty — hidden files (e.g. ``.DS_Store``)
    count too, per ADR-0006's strict "empty / non-existent" contract.
    """
    if flow == "take_over":
        if (project_root / ".git").is_dir():
            return PreflightCheck(
                name="git_state", passed=True, message="目录是 git 仓库"
            )
        return PreflightCheck(
            name="git_state",
            passed=False,
            message="目录不是 git 仓库 (缺少 .git/)",
        )
    # new_project — directory must be empty. Check 1 guarantees the
    # directory exists, so we can iterate safely.
    entries = list(project_root.iterdir())
    if not entries:
        return PreflightCheck(name="git_state", passed=True, message="目录为空")
    return PreflightCheck(
        name="git_state",
        passed=False,
        message="目录非空，新项目流程需要空目录",
    )


def check_clean_tree(project_root: Path, flow: Flow) -> PreflightCheck:
    """Check 3: take_over only. ``git status --porcelain`` must be empty.

    For new_project the check trivially passes — we keep it in the
    result tuple at the same index so the UI's layout doesn't shift
    between flows.

    Failure modes handled:
    - git not on PATH (FileNotFoundError) → user-facing message.
    - git timeout (10s) → user-facing message.
    - non-zero exit → message includes stderr.
    """
    if flow == "new_project":
        return PreflightCheck(
            name="clean_tree", passed=True, message="跳过 (新项目)"
        )

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return PreflightCheck(
            name="clean_tree",
            passed=False,
            message="git 命令不可用，请确保已安装 git 并在 PATH 中",
        )
    except subprocess.TimeoutExpired:
        return PreflightCheck(
            name="clean_tree",
            passed=False,
            message=f"git status 执行超时 ({_GIT_TIMEOUT_SECONDS}秒)，请检查仓库状态",
        )

    if result.returncode != 0:
        return PreflightCheck(
            name="clean_tree",
            passed=False,
            message=f"git status 返回错误码 {result.returncode}: {result.stderr.strip()}",
        )

    if not result.stdout.strip():
        return PreflightCheck(
            name="clean_tree", passed=True, message="工作区干净"
        )
    # Truncate to first 5 porcelain lines so the message stays
    # bounded even on huge dirty trees.
    lines = result.stdout.strip().splitlines()
    sample = "\n".join(lines[:5])
    suffix = "\n..." if len(lines) > 5 else ""
    return PreflightCheck(
        name="clean_tree",
        passed=False,
        message=f"工作区有未提交变更:\n{sample}{suffix}",
    )


def check_no_existing_maestro(project_root: Path, flow: Flow) -> PreflightCheck:
    """Check 4: take_over only. ``.maestro/`` is empty or only has the take-over set.

    For new_project the check trivially passes — check 2's empty-dir
    contract subsumes this case.
    """
    if flow == "new_project":
        return PreflightCheck(
            name="no_existing_maestro", passed=True, message="跳过 (新项目)"
        )

    maestro_dir = project_root / ".maestro"
    if not maestro_dir.exists():
        return PreflightCheck(
            name="no_existing_maestro",
            passed=True,
            message="无 .maestro/ 目录",
        )
    if not maestro_dir.is_dir():
        # Pathological: .maestro is a regular file or symlink to one.
        return PreflightCheck(
            name="no_existing_maestro",
            passed=False,
            message=".maestro 不是一个目录",
        )

    existing = {entry.name for entry in maestro_dir.iterdir()}
    unexpected = existing - _TAKE_OVER_MAESTRO_FILES
    if unexpected:
        listed = ", ".join(sorted(unexpected))
        return PreflightCheck(
            name="no_existing_maestro",
            passed=False,
            message=f"已存在的 .maestro/ 包含 take-over 范围外的内容: {listed}",
        )
    return PreflightCheck(
        name="no_existing_maestro",
        passed=True,
        message="已存在 .maestro/.gitignore (将由 plan 评估)",
    )


def run_preflight(project_root: Path, flow: Flow) -> tuple[PreflightCheck, ...]:
    """Run all 4 checks in order and return their results as a tuple.

    The order is stable: ``directory_exists``, ``git_state``,
    ``clean_tree``, ``no_existing_maestro``. The UI indexes by
    ``.name`` for layout decisions; positional order is also stable.
    """
    return (
        check_directory_exists(project_root),
        check_git_state(project_root, flow),
        check_clean_tree(project_root, flow),
        check_no_existing_maestro(project_root, flow),
    )
