"""Tests for maestro.webui.launcher: port-scan, settings.yaml fallback, CLI override."""

import socket
from contextlib import ExitStack, contextmanager
from pathlib import Path

import pytest

from maestro.webui import launcher


@pytest.fixture
def unused_tcp_port():
    """Allocate a free TCP port on 127.0.0.1 (kernel-assigned)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def unused_tcp_port_factory():
    """Factory returning a callable that yields fresh free ports each call."""
    def _factory():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port
    return _factory


@contextmanager
def _occupy(port: int):
    """Occupy a port on 127.0.0.1 for testing."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", port))
    s.listen(1)
    try:
        yield
    finally:
        s.close()


def test_default_port_constant_is_19830():
    """Verify the default port constant."""
    assert launcher.DEFAULT_PORT == 19830


def test_scan_range_constant_is_10():
    """Verify the scan range constant."""
    assert launcher.SCAN_RANGE == 10


def test_find_free_port_returns_preferred_when_available(unused_tcp_port):
    """When the preferred port is free, it should be returned immediately."""
    assert launcher.find_free_port(unused_tcp_port) == unused_tcp_port


def test_find_free_port_skips_to_next_when_preferred_taken(unused_tcp_port):
    """When the preferred port is taken, the function should try the next port."""
    with _occupy(unused_tcp_port):
        found = launcher.find_free_port(unused_tcp_port)
        assert found >= unused_tcp_port + 1


def test_find_free_port_raises_when_all_taken(unused_tcp_port_factory):
    """When all ports in the range are occupied, a RuntimeError with hint must be raised."""
    base = unused_tcp_port_factory()
    try:
        with ExitStack() as stack:
            for offset in range(launcher.SCAN_RANGE + 1):
                port = base + offset
                stack.enter_context(_occupy(port))
            with pytest.raises(RuntimeError, match="--port"):
                launcher.find_free_port(base)
    except OSError:
        pytest.skip("could not reserve contiguous range")


def test_read_preferred_port_returns_default_when_settings_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Missing settings file should cause a fallback to DEFAULT_PORT."""
    monkeypatch.setattr(
        "maestro.paths.user_settings_path", lambda: tmp_path / "missing.yaml"
    )
    assert launcher.read_preferred_port() == 19830


def test_read_preferred_port_reads_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A valid settings file should provide the port."""
    p = tmp_path / "settings.yaml"
    p.write_text("port: 12345")
    monkeypatch.setattr("maestro.paths.user_settings_path", lambda: p)
    assert launcher.read_preferred_port() == 12345


def test_read_preferred_port_falls_back_on_malformed_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A malformed YAML file should not crash, just fall back to default."""
    p = tmp_path / "settings.yaml"
    p.write_text(": this is not yaml :")
    monkeypatch.setattr("maestro.paths.user_settings_path", lambda: p)
    assert launcher.read_preferred_port() == 19830


def test_read_preferred_port_falls_back_on_non_int_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """If the port value is not an integer, fall back to default."""
    p = tmp_path / "settings.yaml"
    p.write_text("port: not-a-number")
    monkeypatch.setattr("maestro.paths.user_settings_path", lambda: p)
    assert launcher.read_preferred_port() == 19830


def test_main_cli_port_override_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The --port CLI flag should override the settings file value."""
    captured = {}

    def stub(*args, **kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(launcher.uvicorn, "run", stub)
    exit_code = launcher.main(["--port", "23456"])
    assert exit_code == 0
    assert captured["port"] == 23456


def test_main_uses_settings_when_no_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """When no --port is given, the port from settings.yaml should be used."""
    p = tmp_path / "settings.yaml"
    p.write_text("port: 24680")
    monkeypatch.setattr("maestro.paths.user_settings_path", lambda: p)

    captured = {}

    def stub(*args, **kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(launcher.uvicorn, "run", stub)
    exit_code = launcher.main([])
    assert exit_code == 0
    assert captured["port"] == 24680


def test_main_returns_2_when_all_ports_taken(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """If no port can be found, the program should exit with code 2 and print a hint."""

    def fake_find_free_port(*args, **kwargs):
        raise RuntimeError(
            "Ports X–Y are all in use; pass --port N to override."
        )

    monkeypatch.setattr(launcher, "find_free_port", fake_find_free_port)
    called = False

    def stub(*args, **kwargs):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(launcher.uvicorn, "run", stub)
    exit_code = launcher.main([])
    assert exit_code == 2
    assert called is False
    captured = capsys.readouterr()
    assert "--port" in captured.err
