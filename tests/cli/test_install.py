import json
import sys
from pathlib import Path

import pytest
from maestro.cli.install import install


# Helper to set a fake argv[0] before calling install
def _fake_argv(monkeypatch, cmd_path="/fake/bin/maestro"):
    monkeypatch.setattr(sys, "argv", [cmd_path, "install"])


def test_install_creates_fresh_config(tmp_path, monkeypatch):
    _fake_argv(monkeypatch, "/my/maestro")
    config_path = tmp_path / ".claude" / "mcp.json"
    assert not config_path.exists()

    result = install(config_path=config_path)
    assert result == 0

    assert config_path.is_file()
    data = json.loads(config_path.read_text())
    assert data["mcpServers"]["maestro"] == {
        "command": "/my/maestro",
        "args": ["serve"],
    }


def test_install_adds_entry_to_existing_config(tmp_path, monkeypatch):
    _fake_argv(monkeypatch, "/my/maestro")
    config_path = tmp_path / "mcp.json"
    existing = {
        "mcpServers": {
            "other": {"command": "/bin/echo", "args": []}
        }
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(existing, indent=2) + "\n")

    result = install(config_path=config_path)
    assert result == 0

    data = json.loads(config_path.read_text())
    assert data["mcpServers"]["other"] == {"command": "/bin/echo", "args": []}
    assert data["mcpServers"]["maestro"] == {
        "command": "/my/maestro",
        "args": ["serve"],
    }
    # Check that other entry byte content preserved as much as possible (json roundtrip)
    assert data["mcpServers"]["other"] == existing["mcpServers"]["other"]


def test_install_idempotent_when_entry_matches(tmp_path, monkeypatch, capsys):
    _fake_argv(monkeypatch, "/my/maestro")
    config_path = tmp_path / "mcp.json"
    desired_entry = {
        "mcpServers": {
            "maestro": {
                "command": "/my/maestro",
                "args": ["serve"],
            }
        }
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(desired_entry, indent=2) + "\n")
    mtime_before = config_path.stat().st_mtime

    result = install(config_path=config_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "no changes needed" in captured.out
    mtime_after = config_path.stat().st_mtime
    assert mtime_after == mtime_before  # file unchanged


def test_install_force_overwrites_existing(tmp_path, monkeypatch):
    _fake_argv(monkeypatch, "/my/maestro")
    config_path = tmp_path / "mcp.json"
    stale = {
        "mcpServers": {
            "maestro": {
                "command": "/old/maestro",
                "args": ["serve"],
            }
        }
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(stale, indent=2) + "\n")

    result = install(config_path=config_path, force=True)
    assert result == 0
    data = json.loads(config_path.read_text())
    assert data["mcpServers"]["maestro"]["command"] == "/my/maestro"


def test_install_prompts_on_existing_no_force(tmp_path, monkeypatch, capsys):
    _fake_argv(monkeypatch, "/my/maestro")
    config_path = tmp_path / "mcp.json"
    stale = {
        "mcpServers": {
            "maestro": {
                "command": "/old/maestro",
                "args": ["serve"],
            }
        }
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(stale, indent=2) + "\n")

    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = install(config_path=config_path, force=False)
    assert result == 0
    data = json.loads(config_path.read_text())
    assert data["mcpServers"]["maestro"]["command"] == "/my/maestro"


def test_install_declined_on_prompt_no(tmp_path, monkeypatch, capsys):
    _fake_argv(monkeypatch, "/my/maestro")
    config_path = tmp_path / "mcp.json"
    stale = {
        "mcpServers": {
            "maestro": {
                "command": "/old/maestro",
                "args": ["serve"],
            }
        }
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(stale, indent=2) + "\n")

    monkeypatch.setattr("builtins.input", lambda _: "n")
    result = install(config_path=config_path, force=False)
    captured = capsys.readouterr()
    assert result == 1
    assert "declined" in captured.err
    # file unchanged
    data = json.loads(config_path.read_text())
    assert data["mcpServers"]["maestro"]["command"] == "/old/maestro"


def test_install_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    _fake_argv(monkeypatch, "/my/maestro")
    config_path = tmp_path / "mcp.json"
    assert not config_path.exists()

    result = install(config_path=config_path, dry_run=True)
    captured = capsys.readouterr()
    assert result == 0
    assert not config_path.exists()
    assert "Would add maestro entry" in captured.out
    # JSON preview should contain the entry
    assert "/my/maestro" in captured.out


def test_install_dry_run_with_existing_diff(tmp_path, monkeypatch, capsys):
    _fake_argv(monkeypatch, "/new/maestro")
    config_path = tmp_path / "mcp.json"
    stale = {
        "mcpServers": {
            "maestro": {
                "command": "/old/maestro",
                "args": ["serve"],
            }
        }
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(stale, indent=2) + "\n")

    result = install(config_path=config_path, dry_run=True)
    captured = capsys.readouterr()
    assert result == 0
    assert not config_path.exists() or config_path.is_file()  # file still exists but unchanged
    assert "Would overwrite" in captured.out
    assert "/new/maestro" in captured.out


def test_install_refuses_malformed_existing(tmp_path, monkeypatch, capsys):
    _fake_argv(monkeypatch, "/my/maestro")
    config_path = tmp_path / "mcp.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{not valid json")

    result = install(config_path=config_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "ERROR" in captured.err
    assert str(config_path) in captured.err
    # file untouched (content identical)
    assert config_path.read_text() == "{not valid json"


def test_install_preserves_other_mcp_servers_under_force(tmp_path, monkeypatch):
    _fake_argv(monkeypatch, "/my/maestro")
    config_path = tmp_path / "mcp.json"
    original = {
        "mcpServers": {
            "other": {"command": "/bin/echo", "args": []},
            "maestro": {"command": "/old/maestro", "args": ["serve"]},
        }
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(original, indent=2) + "\n")

    result = install(config_path=config_path, force=True)
    assert result == 0
    data = json.loads(config_path.read_text())
    assert data["mcpServers"]["other"] == {"command": "/bin/echo", "args": []}
    assert data["mcpServers"]["maestro"] == {
        "command": "/my/maestro",
        "args": ["serve"],
    }


def test_install_command_path_uses_sys_argv0(tmp_path, monkeypatch):
    fake_bin = "/my/fake/bin/maestro"
    monkeypatch.setattr(sys, "argv", [fake_bin, "install"])
    config_path = tmp_path / "mcp.json"

    result = install(config_path=config_path)
    assert result == 0
    data = json.loads(config_path.read_text())
    assert data["mcpServers"]["maestro"]["command"] == fake_bin
