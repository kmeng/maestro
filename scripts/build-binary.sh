#!/usr/bin/env bash
# Maestro native binary build script (Epic 10 / T10.2)
#
# Creates a clean build venv, installs runtime + pyinstaller, runs the
# spec, and verifies the resulting binary by invoking `--version` and
# `install --dry-run --config-path <tmp>`.
#
# Usage:
#     bash scripts/build-binary.sh
# Output:
#     dist/maestro     (single-file executable)
#     Verification PASS/FAIL summary on stdout.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

venv_dir=".venv-build"
build_dir="build"
dist_dir="dist"

echo "==> Cleaning build artifacts"
rm -rf "$build_dir" "$dist_dir" "$venv_dir"

echo "==> Creating fresh build venv at $venv_dir"
python3 -m venv "$venv_dir"
source "$venv_dir/bin/activate"

echo "==> Installing runtime + pyinstaller"
pip install --quiet --upgrade pip
pip install --quiet -e .
pip install --quiet pyinstaller
# Also install non-pyproject runtime deps from bootstrap/requirements.txt
# (mcp, openai, python-dotenv are not yet in pyproject.toml's dependencies
# but are required at runtime).
pip install --quiet -r bootstrap/requirements.txt

echo "==> Running PyInstaller"
pyinstaller pyinstaller.spec --noconfirm

binary="$dist_dir/maestro"
if [ ! -x "$binary" ]; then
    echo "FAIL: $binary not produced or not executable"
    exit 1
fi

echo "==> Verifying binary: --version"
version_out=$("$binary" --version)
expected_prefix="maestro 0.1.0"
if ! echo "$version_out" | grep -q "^$expected_prefix"; then
    echo "FAIL: expected '$expected_prefix' from --version, got '$version_out'"
    exit 1
fi
echo "  ok: $version_out"

echo "==> Verifying binary: install --dry-run (isolated config)"
tmp_config="$(mktemp -d)/mcp.json"
"$binary" install --dry-run --config-path "$tmp_config"
if [ -f "$tmp_config" ]; then
    echo "FAIL: dry-run wrote $tmp_config (must not write)"
    exit 1
fi
echo "  ok: dry-run wrote nothing"

binary_size=$(du -h "$binary" | cut -f1)
echo
echo "==> Build complete"
echo "  binary: $binary ($binary_size)"
echo "  PASS"
