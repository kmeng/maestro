"""Unit tests for scaffolding pre-flight checks (T2.3).

Includes the load-bearing **conversion test** at the bottom: asserts
that T2.3's additive change to Plan (the new ``preflight`` field with
default ``()``) does not break any T2.1-era construction.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from maestro.scaffold.operations import (
    Operation,
    Plan,
    PlanRow,
    PreflightCheck,
)
from maestro.scaffold.preflight import (
    check_clean_tree,
    check_directory_exists,
    check_git_state,
    check_no_existing_maestro,
    run_preflight,
)
import maestro.scaffold.preflight as pf

# Captured at module import — BEFORE conftest.py's autouse fixture
# monkeypatches subprocess.run with a stub that returns returncode=128.
# We use this real reference for _git_init and inside preflight tests
# that need actual git via monkeypatch override.
_REAL_SUBPROCESS_RUN = subprocess.run


@pytest.fixture
def real_git(monkeypatch):
    """Restore real subprocess.run for tests that need actual git.

    Overrides the autouse conftest fixture that stubs subprocess.run
    (which exists to neutralize git branch inference in T6.8 attribution
    tests). Returns nothing — just the side effect of restoring the
    real subprocess.run.
    """
    monkeypatch.setattr(subprocess, "run", _REAL_SUBPROCESS_RUN)
    monkeypatch.setattr(pf.subprocess, "run", _REAL_SUBPROCESS_RUN)


def _git_init(repo: Path) -> None:
    """Init a git repo + set user identity (CI environments may lack a global).

    Uses the real subprocess.run captured at module import, since the
    autouse conftest fixture would otherwise stub git out.
    """
    _REAL_SUBPROCESS_RUN(
        ["git", "init"], cwd=str(repo), check=True, capture_output=True,
    )
    _REAL_SUBPROCESS_RUN(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo), check=True, capture_output=True,
    )
    _REAL_SUBPROCESS_RUN(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo), check=True, capture_output=True,
    )


def _git_commit_initial(repo: Path) -> None:
    """Add + commit an initial dummy file so the repo has a clean HEAD."""
    (repo / "dummy").write_text("initial")
    _REAL_SUBPROCESS_RUN(
        ["git", "add", "dummy"], cwd=str(repo), check=True, capture_output=True,
    )
    _REAL_SUBPROCESS_RUN(
        ["git", "commit", "-m", "init"],
        cwd=str(repo), check=True, capture_output=True,
    )


# -- check_directory_exists -------------------------------------------------

def test_check_directory_exists_passes_on_real_dir(tmp_path: Path) -> None:
    result = check_directory_exists(tmp_path)
    assert result.passed is True
    assert "目录存在" in result.message


def test_check_directory_exists_fails_on_nonexistent_path(tmp_path: Path) -> None:
    result = check_directory_exists(tmp_path / "nope")
    assert result.passed is False
    assert "目录不存在" in result.message


def test_check_directory_exists_fails_on_file_not_dir(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("content")
    result = check_directory_exists(file_path)
    assert result.passed is False
    assert "目录不存在" in result.message


# -- check_git_state --------------------------------------------------------

def test_check_git_state_take_over_passes_on_git_repo(tmp_path: Path) -> None:
    _git_init(tmp_path)
    result = check_git_state(tmp_path, "take_over")
    assert result.passed is True
    assert "git 仓库" in result.message


def test_check_git_state_take_over_fails_on_non_git(tmp_path: Path) -> None:
    result = check_git_state(tmp_path, "take_over")
    assert result.passed is False
    assert "缺少 .git/" in result.message


def test_check_git_state_new_project_passes_on_empty_dir(tmp_path: Path) -> None:
    result = check_git_state(tmp_path, "new_project")
    assert result.passed is True
    assert "目录为空" in result.message


def test_check_git_state_new_project_fails_on_populated_dir(tmp_path: Path) -> None:
    (tmp_path / "readme.md").touch()
    result = check_git_state(tmp_path, "new_project")
    assert result.passed is False
    assert "目录非空" in result.message


def test_check_git_state_new_project_fails_on_hidden_entries(tmp_path: Path) -> None:
    (tmp_path / ".DS_Store").touch()
    result = check_git_state(tmp_path, "new_project")
    assert result.passed is False
    assert "目录非空" in result.message


# -- check_clean_tree -------------------------------------------------------

def test_check_clean_tree_passes_on_clean_repo(tmp_path: Path, real_git) -> None:
    _git_init(tmp_path)
    _git_commit_initial(tmp_path)
    result = check_clean_tree(tmp_path, "take_over")
    assert result.passed is True
    assert "工作区干净" in result.message


def test_check_clean_tree_fails_on_dirty_repo(tmp_path: Path, real_git) -> None:
    _git_init(tmp_path)
    (tmp_path / "readme.md").write_text("hello")
    result = check_clean_tree(tmp_path, "take_over")
    assert result.passed is False
    assert "未提交变更" in result.message


def test_check_clean_tree_skipped_for_new_project(tmp_path: Path) -> None:
    result = check_clean_tree(tmp_path, "new_project")
    assert result.passed is True
    assert "跳过 (新项目)" in result.message


def test_check_clean_tree_handles_git_missing(tmp_path: Path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("git not found")
    monkeypatch.setattr(pf.subprocess, "run", fake_run)
    result = check_clean_tree(tmp_path, "take_over")
    assert result.passed is False
    assert "git 命令不可用" in result.message


def test_check_clean_tree_handles_timeout(tmp_path: Path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["git", "status"], timeout=10)
    monkeypatch.setattr(pf.subprocess, "run", fake_run)
    result = check_clean_tree(tmp_path, "take_over")
    assert result.passed is False
    assert "超时" in result.message


# -- check_no_existing_maestro ---------------------------------------------

def test_check_no_existing_maestro_passes_when_absent(tmp_path: Path) -> None:
    result = check_no_existing_maestro(tmp_path, "take_over")
    assert result.passed is True
    assert "无 .maestro/" in result.message


def test_check_no_existing_maestro_passes_when_only_gitignore(tmp_path: Path) -> None:
    maestro_dir = tmp_path / ".maestro"
    maestro_dir.mkdir()
    (maestro_dir / ".gitignore").write_text("# maestro")
    result = check_no_existing_maestro(tmp_path, "take_over")
    assert result.passed is True
    assert "已存在 .maestro/.gitignore" in result.message


def test_check_no_existing_maestro_fails_when_team_yaml_exists(tmp_path: Path) -> None:
    maestro_dir = tmp_path / ".maestro"
    maestro_dir.mkdir()
    (maestro_dir / "team.yaml").write_text("team: A")
    result = check_no_existing_maestro(tmp_path, "take_over")
    assert result.passed is False
    assert "team.yaml" in result.message


def test_check_no_existing_maestro_skipped_for_new_project(tmp_path: Path) -> None:
    result = check_no_existing_maestro(tmp_path, "new_project")
    assert result.passed is True
    assert "跳过 (新项目)" in result.message


# -- run_preflight ----------------------------------------------------------

def test_run_preflight_returns_tuple_in_stable_order(tmp_path: Path) -> None:
    results = run_preflight(tmp_path, "new_project")
    assert len(results) == 4
    assert [r.name for r in results] == [
        "directory_exists", "git_state", "clean_tree", "no_existing_maestro",
    ]


def test_run_preflight_all_pass_on_clean_git_repo_with_no_maestro(tmp_path: Path, real_git) -> None:
    _git_init(tmp_path)
    _git_commit_initial(tmp_path)
    results = run_preflight(tmp_path, "take_over")
    assert all(r.passed for r in results)


# -- Conversion test — Plan backward compatibility (load-bearing) ----------

def test_plan_construction_backward_compatible() -> None:
    """T2.1-era construction MUST still work after T2.3 adds preflight.

    This is the discipline imposed by `feedback_migration_needs_conversion_test.md`:
    when extending an existing structure, verify the conversion path
    (callers that constructed it the old way) still works.
    """
    # T2.1-style construction (no preflight argument) — must work
    p = Plan(rows=(PlanRow(path="x", op=Operation.CREATE, detail="x"),))
    assert p.preflight == ()

    # Equality on empty plans still works
    assert Plan(rows=()) == Plan(rows=())

    # Plans with different preflight are NOT equal
    diff = Plan(rows=(), preflight=(PreflightCheck("x", True, "y"),))
    assert Plan(rows=()) != diff
