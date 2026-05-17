# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Maestro native binary (Epic 10 / T10.2).

Builds a single-file `maestro` binary that bundles:
  - maestro CLI (entry: maestro.cli.main:main)
  - MCP server (maestro.mcp_server)
  - Web UI (maestro.webui.* + Jinja2 templates + static assets)
  - All Python runtime dependencies

Build:
    pyinstaller pyinstaller.spec
Output:
    dist/maestro             # macOS / Linux single executable
    dist/maestro.exe         # Windows single executable

The bundled deps include fastapi / uvicorn / mcp / pydantic v2 which
require hidden-import hints that PyInstaller cannot infer automatically.
The `hiddenimports` list below was determined empirically. Add to it
when you see ModuleNotFoundError at runtime in `dist/maestro serve` or
`dist/maestro webui`.
"""

import sys
from pathlib import Path

block_cipher = None
repo_root = Path(SPECPATH).resolve()

# ============================================================
# Data files — non-Python assets that must travel with the binary.
# PyInstaller does NOT honour setuptools package-data; declare explicitly.
# ============================================================

datas = [
    # Web UI templates (Jinja2)
    (str(repo_root / "maestro" / "webui" / "templates"), "maestro/webui/templates"),
    # Web UI static assets
    (str(repo_root / "maestro" / "webui" / "static"), "maestro/webui/static"),
    # Scaffold templates (used by `maestro` scaffolding flows)
    (str(repo_root / "maestro" / "scaffold" / "templates"), "maestro/scaffold/templates"),
]

# ============================================================
# Hidden imports — modules PyInstaller's static analyser cannot trace
# because they are imported dynamically (uvicorn loop selection,
# pydantic v2 plugin discovery, mcp protocol-version registry, etc.).
# ============================================================

hiddenimports = [
    # uvicorn dynamic loop / protocol selection
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.logging",
    # fastapi internals
    "email_validator",
    # pydantic v2
    "pydantic.deprecated.decorator",
    # mcp SDK stdio path
    "mcp.server",
    "mcp.server.stdio",
    "mcp.types",
    # openai SDK (used as DeepSeek/Qwen client)
    "openai",
    # dotenv (env loading)
    "dotenv",
]

a = Analysis(
    [str(repo_root / "maestro" / "cli" / "main.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Test-only deps — don't ship them
        "pytest",
        "pytest_asyncio",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="maestro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # keep symbols for debuggability; macOS will not sign-strip
    upx=False,    # UPX compression breaks macOS code signing (irrelevant in v0.1) and inflates startup
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # MCP server reads stdio; must be a console binary
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # v0.1 unsigned; documented Gatekeeper bypass
    entitlements_file=None,
)
