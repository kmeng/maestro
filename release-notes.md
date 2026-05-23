# Maestro <tag>

## What's new

(Edit before tagging.)

## Install

Download the artifact for your OS from the Assets below:

- **macOS (Apple Silicon)** — `maestro-macos-arm64.tar.gz`
- **Linux x64** — `maestro-linux-x64.tar.gz`
- **Windows x64** — `maestro-windows-x64.zip`

Extract, place `maestro` on your PATH, then:

```
maestro install
```

This writes `~/.claude/mcp.json` registering Maestro with Claude Code.
Restart Claude Code and run `/mcp` to verify the connection.

### macOS first-run note

The binary is unsigned in this release. macOS Gatekeeper will block it
on first run with "developer cannot be verified". To bypass:

1. In Finder, right-click `maestro` → Open → Open in the dialog.
2. After approving once, all subsequent runs work normally.

Code signing + notarization is planned for a future release.

## See also

- [Upgrade guide](docs/ops/mcp-reload.md) — Claude Code needs a reconnect after upgrade
- [Build doc](docs/ops/binary-build.md) — how to build the binary yourself

## 社区 / Community

Maestro 由 **挖宝的瓦力** 维护。关注公众号获取 AI 协作方法论与更新，或加微信直接反馈——二维码见仓库 [README「社区 / 联系」](https://github.com/kmeng/maestro#community--contact)。Bug 与建议欢迎来 [GitHub Issues](https://github.com/kmeng/maestro/issues)。
