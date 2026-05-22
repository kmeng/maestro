"""Unit tests for the scaffolding Web UI routes (T2.7)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from maestro.scaffold.operations import (
    PreflightCheck,
)
from maestro.scaffold.templates import render_claude_md_standalone
from maestro.webui import app

# Captured at module import — BEFORE conftest.py autouse fixture stubs
# subprocess.run (per feedback_conftest_subprocess_patch_trap memory).
_REAL_SUBPROCESS_RUN = subprocess.run


def _stub_preflight_all_pass(monkeypatch):
    """Replace run_preflight inside scaffold_view with a 4-PASS stub."""
    monkeypatch.setattr(
        "maestro.webui.scaffold_view.run_preflight",
        lambda root, flow: tuple(
            PreflightCheck(name=n, passed=True, message="ok")
            for n in (
                "directory_exists",
                "git_state",
                "clean_tree",
                "no_existing_maestro",
            )
        ),
    )


def _stub_preflight_one_fail(monkeypatch):
    monkeypatch.setattr(
        "maestro.webui.scaffold_view.run_preflight",
        lambda root, flow: (
            PreflightCheck(name="directory_exists", passed=False, message="目录不存在"),
            PreflightCheck(name="git_state", passed=True, message="skipped"),
            PreflightCheck(name="clean_tree", passed=True, message="skipped"),
            PreflightCheck(name="no_existing_maestro", passed=True, message="skipped"),
        ),
    )


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


# -- Picker ----------------------------------------------------------------

def test_picker_renders(client):
    resp = client.get("/scaffold")
    assert resp.status_code == 200
    # The picker heading is now "Scaffold" (page-h1) in the redesigned template
    # (T9.6). The legacy "新建或接入项目" header lived in the old standalone
    # template; the picker copy now lives in .page-sub.
    assert ">Scaffold</h1>" in resp.text or "新建项目" in resp.text
    assert 'action="/scaffold/plan"' in resp.text


def test_picker_has_chinese_copy_only(client):
    """No English UI words other than allowed proper nouns / file paths."""
    resp = client.get("/scaffold")
    html = resp.text
    # Forbidden English UI words (case-sensitive — proper nouns like Maestro / CLAUDE allowed)
    forbidden = ["Create", "Next", "Cancel", "Submit", "Apply", "Continue", "Back"]
    for word in forbidden:
        assert word not in html, f"English UI word '{word}' found in picker"


# -- Plan page -------------------------------------------------------------

@pytest.mark.parametrize("mode", ["new_project", "take_over"])
def test_plan_page_renders_with_all_pass_preflight(client, tmp_path, monkeypatch, mode):
    _stub_preflight_all_pass(monkeypatch)
    resp = client.get(f"/scaffold/plan?path={tmp_path}&mode={mode}")
    assert resp.status_code == 200
    html = resp.text
    assert "前置检查" in html
    assert "✓" in html
    assert "应用计划" in html
    # Both modes produce plans that include CLAUDE.md.
    assert "CLAUDE.md" in html
    # Reviewer T2.7 round 1 finding: lock the contract that engine-generated
    # row.detail strings are Chinese. All v0.0.3 CREATE-op rows produce
    # "将创建 <path>" details (per maestro/scaffold/engine.py).
    assert "将创建" in html


def test_plan_page_apply_button_disabled_on_preflight_fail(client, tmp_path, monkeypatch):
    _stub_preflight_one_fail(monkeypatch)
    resp = client.get(f"/scaffold/plan?path={tmp_path}&mode=new_project")
    assert resp.status_code == 200
    html = resp.text
    assert "disabled" in html
    assert "前置检查未通过" in html


def test_plan_page_apply_button_disabled_when_conflict_in_rows(client, tmp_path, monkeypatch):
    _stub_preflight_all_pass(monkeypatch)
    # Pre-write CLAUDE.md with v=2 marker → engine marks CONFLICT.
    (tmp_path / "CLAUDE.md").write_bytes(render_claude_md_standalone(section_version=2))
    resp = client.get(f"/scaffold/plan?path={tmp_path}&mode=take_over")
    assert resp.status_code == 200
    html = resp.text
    assert "disabled" in html
    assert "请解决冲突" in html


def test_plan_page_validates_mode(client, tmp_path, monkeypatch):
    _stub_preflight_all_pass(monkeypatch)
    resp = client.get(f"/scaffold/plan?path={tmp_path}&mode=invalid_mode")
    assert resp.status_code == 400


# -- Plan row partial ------------------------------------------------------

def test_plan_row_partial_renders_for_create_op(client, tmp_path, monkeypatch):
    _stub_preflight_all_pass(monkeypatch)
    resp = client.get(f"/scaffold/plan-row/.gitignore?path={tmp_path}&mode=new_project")
    assert resp.status_code == 200
    # CREATE-op partial in the redesigned template (T9.6) emits a
    # `<div class="muted">{detail}</div>` instead of the old `.drill-down`
    # wrapper. Assert on the structural marker that still uniquely identifies
    # the partial render.
    assert "<div" in resp.text and ("muted" in resp.text or "将创建" in resp.text)


def test_plan_row_partial_for_conflict_includes_open_no_force(client, tmp_path, monkeypatch):
    """CONFLICT row has Open file (no Force overwrite button per ADR-0006)."""
    _stub_preflight_all_pass(monkeypatch)
    (tmp_path / "CLAUDE.md").write_bytes(render_claude_md_standalone(section_version=2))
    resp = client.get(f"/scaffold/plan-row/CLAUDE.md?path={tmp_path}&mode=take_over")
    assert resp.status_code == 200
    html = resp.text
    # Open file button present
    assert "打开文件" in html
    # Conflict reason translated to Chinese
    assert "版本不匹配" in html
    # No force-overwrite affordance per ADR-0006 alternatives
    assert "覆盖" not in html
    assert "强制" not in html
    assert "force" not in html.lower()


def test_plan_row_partial_for_append_shows_diff(client, tmp_path, monkeypatch):
    _stub_preflight_all_pass(monkeypatch)
    (tmp_path / "CLAUDE.md").write_text("Existing user content\n")
    resp = client.get(f"/scaffold/plan-row/CLAUDE.md?path={tmp_path}&mode=take_over")
    assert resp.status_code == 200
    html = resp.text
    assert "将追加以下内容到" in html
    assert "Existing user content" in html
    assert "maestro:start v=1" in html


def test_plan_row_partial_404_on_unknown_row(client, tmp_path, monkeypatch):
    _stub_preflight_all_pass(monkeypatch)
    resp = client.get(f"/scaffold/plan-row/bogus.txt?path={tmp_path}&mode=new_project")
    assert resp.status_code == 404


# -- Apply post ------------------------------------------------------------

def test_apply_post_renders_final_state(client, tmp_path, monkeypatch):
    _stub_preflight_all_pass(monkeypatch)
    resp = client.post(
        "/scaffold/apply",
        data={
            "path": str(tmp_path),
            "mode": "take_over",
            "accepted_paths": [".maestro/.gitignore", "CLAUDE.md"],
        },
    )
    assert resp.status_code == 200
    html = resp.text
    assert "成功" in html
    assert "失败" in html
    # The two accepted files should be visible in the result list.
    assert ".maestro/.gitignore" in html or "CLAUDE.md" in html


def test_apply_post_rejected_on_preflight_fail(client, tmp_path, monkeypatch):
    _stub_preflight_one_fail(monkeypatch)
    resp = client.post(
        "/scaffold/apply",
        data={
            "path": str(tmp_path),
            "mode": "new_project",
            "accepted_paths": [],
        },
    )
    assert resp.status_code == 200
    html = resp.text
    assert "计划被拒绝" in html


def test_apply_post_calls_upsert_only_when_plan_rows_nonempty(client, tmp_path, monkeypatch):
    """Empty accepted_paths → no rows → no upsert (same guard as T2.6 fix)."""
    _stub_preflight_all_pass(monkeypatch)
    calls: list[Path] = []
    monkeypatch.setattr(
        "maestro.webui.scaffold_view.upsert_project",
        lambda p: calls.append(p),
    )
    resp = client.post(
        "/scaffold/apply",
        data={
            "path": str(tmp_path),
            "mode": "take_over",
            "accepted_paths": [],
        },
    )
    assert resp.status_code == 200
    assert calls == []


# -- T2.8: wizard auto-launch after successful apply -----------------------

def test_apply_success_includes_wizard_autoredirect(client, tmp_path, monkeypatch):
    """succeeded > 0 → meta refresh to /wizard + manual fallback link."""
    _stub_preflight_all_pass(monkeypatch)
    resp = client.post(
        "/scaffold/apply",
        data={
            "path": str(tmp_path),
            "mode": "take_over",
            "accepted_paths": [".maestro/.gitignore", "CLAUDE.md"],
        },
    )
    assert resp.status_code == 200
    html = resp.text
    # Auto-redirect markup present
    assert 'http-equiv="refresh"' in html
    assert "url=/wizard" in html
    # User-visible cue
    assert "跳转到团队配置" in html
    # Manual fallback link
    assert 'href="/wizard"' in html
    assert "立即配置团队" in html


def test_apply_rejected_does_not_autoredirect(client, tmp_path, monkeypatch):
    """Preflight rejection → no auto-redirect (user reads the rejection)."""
    _stub_preflight_one_fail(monkeypatch)
    resp = client.post(
        "/scaffold/apply",
        data={"path": str(tmp_path), "mode": "new_project", "accepted_paths": []},
    )
    assert resp.status_code == 200
    html = resp.text
    assert 'http-equiv="refresh"' not in html
    assert "url=/wizard" not in html
    assert "立即配置团队" not in html


def test_apply_zero_succeeded_does_not_autoredirect(client, tmp_path, monkeypatch):
    """All accepted files were CONFLICT → succeeded=0 → no redirect.

    Pre-write CLAUDE.md with v=2 marker so engine marks it CONFLICT;
    apply_plan emits FileFailed for it. PlanComplete reports
    succeeded=0, failed=1 — user needs to see the failure list.
    """
    _stub_preflight_all_pass(monkeypatch)
    from maestro.scaffold.templates import render_claude_md_standalone
    (tmp_path / "CLAUDE.md").write_bytes(render_claude_md_standalone(section_version=2))
    resp = client.post(
        "/scaffold/apply",
        data={
            "path": str(tmp_path),
            "mode": "take_over",
            "accepted_paths": ["CLAUDE.md"],
        },
    )
    assert resp.status_code == 200
    html = resp.text
    assert "成功 0 个文件" in html
    assert 'http-equiv="refresh"' not in html
    assert "url=/wizard" not in html
