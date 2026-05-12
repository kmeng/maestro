"""Tests for the team.yaml HTTP API endpoints."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maestro.team import (
    DEFAULT_MODELS,
    TeamConfig,
    save_team_config,
)
from maestro.webui.team_api import router


@pytest.fixture
def app(monkeypatch, tmp_path):
    """Build a FastAPI app with the team_api router mounted.

    Monkeypatches the project_root resolver to point at tmp_path so each
    test gets its own isolated .maestro/ directory.
    """
    monkeypatch.setattr("maestro.webui.team_api._project_root", lambda: tmp_path)
    fastapi_app = FastAPI()
    fastapi_app.include_router(router)
    return fastapi_app


@pytest.fixture
def client(app):
    return TestClient(app)


def _valid_payload() -> dict:
    """Round-trippable POST payload matching the schema."""
    return {
        "schema_version": 1,
        "roles": {
            "coder": {"member": "Cody", "model": DEFAULT_MODELS["coder"]},
            "librarian": {"member": "Lily", "model": DEFAULT_MODELS["librarian"]},
            "reviewer": {"member": "Rae", "model": DEFAULT_MODELS["reviewer"]},
            "scribe": {"member": "Sage", "model": DEFAULT_MODELS["scribe"]},
        },
    }


def test_get_returns_404_when_absent(client):
    """Fresh tmp_path with no team.yaml → 404."""
    resp = client.get("/api/team")
    assert resp.status_code == 404
    assert "not configured" in resp.json()["detail"]


def test_get_returns_200_when_valid(client, tmp_path):
    """Seeded valid team.yaml → 200 with correct structure."""
    cfg = TeamConfig(**_valid_payload())
    save_team_config(tmp_path, cfg)

    resp = client.get("/api/team")
    assert resp.status_code == 200
    data = resp.json()
    assert data["schema_version"] == 1
    assert set(data["roles"].keys()) == {"coder", "librarian", "reviewer", "scribe"}


def test_get_returns_422_on_yaml_parse_error(client, tmp_path):
    """Malformed YAML in team.yaml → 422 with reason containing 'yaml'."""
    maestro_dir = tmp_path / ".maestro"
    maestro_dir.mkdir(parents=True, exist_ok=True)
    (maestro_dir / "team.yaml").write_text(": : :")

    resp = client.get("/api/team")
    assert resp.status_code == 422
    body = resp.json()
    assert isinstance(body["detail"], list)
    assert "yaml" in body["reason"].lower()


def test_get_returns_422_on_validation_error(client, tmp_path):
    """Valid YAML but schema_version: 2 → 422 with detail referencing schema_version."""
    maestro_dir = tmp_path / ".maestro"
    maestro_dir.mkdir(parents=True, exist_ok=True)
    payload = _valid_payload()
    payload["schema_version"] = 2
    import yaml
    (maestro_dir / "team.yaml").write_text(yaml.dump(payload))

    resp = client.get("/api/team")
    assert resp.status_code == 422
    body = resp.json()
    assert isinstance(body["detail"], list)
    assert len(body["detail"]) > 0
    detail_str = str(body["detail"])
    assert "schema_version" in detail_str


def test_post_creates_team_yaml(client, tmp_path):
    """POST valid payload → 201, response matches, file exists."""
    payload = _valid_payload()
    resp = client.post("/api/team", json=payload)
    assert resp.status_code == 201
    assert resp.json() == payload
    assert (tmp_path / ".maestro" / "team.yaml").is_file()


def test_post_returns_422_on_invalid_payload(client):
    """POST with only 1 role → 422."""
    payload = {
        "schema_version": 1,
        "roles": {
            "coder": {"member": "Cody", "model": "deepseek-v4-pro"},
        },
    }
    resp = client.post("/api/team", json=payload)
    assert resp.status_code == 422


def test_post_returns_422_on_unknown_role(client):
    """POST with all 4 valid roles plus an extra 'architect' role → 422."""
    payload = _valid_payload()
    payload["roles"]["architect"] = {"member": "Archie", "model": DEFAULT_MODELS["coder"]}
    resp = client.post("/api/team", json=payload)
    assert resp.status_code == 422


def test_post_returns_422_on_duplicate_member_alias(client):
    """POST where coder.member and librarian.member are case-insensitive duplicates → 422."""
    payload = _valid_payload()
    payload["roles"]["coder"]["member"] = "Cody"
    payload["roles"]["librarian"]["member"] = "cody"
    resp = client.post("/api/team", json=payload)
    assert resp.status_code == 422


def test_post_returns_422_on_bad_model_pattern(client):
    """POST with uppercase model name that fails regex → 422."""
    payload = _valid_payload()
    payload["roles"]["coder"]["model"] = "DeepSeek-V4"
    resp = client.post("/api/team", json=payload)
    assert resp.status_code == 422


def test_post_then_get_round_trip(client):
    """POST with whitespace in member → GET returns canonicalised value."""
    payload = _valid_payload()
    payload["roles"]["coder"]["member"] = "  Cody  "
    resp = client.post("/api/team", json=payload)
    assert resp.status_code == 201

    resp = client.get("/api/team")
    assert resp.status_code == 200
    assert resp.json()["roles"]["coder"]["member"] == "Cody"


def test_post_overwrites_existing(client):
    """POST v1 then POST v2 → GET reflects v2."""
    payload_v1 = _valid_payload()
    payload_v1["roles"]["coder"]["member"] = "Cody"
    client.post("/api/team", json=payload_v1)

    payload_v2 = _valid_payload()
    payload_v2["roles"]["coder"]["member"] = "NewCody"
    client.post("/api/team", json=payload_v2)

    resp = client.get("/api/team")
    assert resp.status_code == 200
    assert resp.json()["roles"]["coder"]["member"] == "NewCody"
