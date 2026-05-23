# Design: 品牌与社区引流 — logo 落地 + WebUI 关于页

**Status**: proposed (2026-05-23)
**Issue**: #132 (epic)
**Related**: `maestro/webui/__init__.py`, `maestro/webui/templates/_base.html`, `maestro/webui/static/maestro.css`, `maestro/webui/static/` (二维码 + logo 资产), 新增 `maestro/webui/about_view.py` + `maestro/webui/templates/about.html`, 新增 `docs/branding/`
**ADR**: 不需要。新增静态展示页是既有 webui 路由模式的**加性**扩展（与 savings/history 等同构）；logo 是品牌资产而非技术架构决策；无新依赖、新角色、新接口、新存储格式。logo 色彩与 WebUI token 的取舍记录在本设计 § Open questions + `docs/branding/` 品牌指南。

## 背景

v1.0 功能完善后做品牌轮（epic #132）。slogan 与 logo 已于 2026-05-23 与维护者敲定：

- **主句**：你来指挥，AI 来演奏 / *You conduct. The AI plays.*
- **副句**：用初级的价，拿资深的活 / *Pay junior prices for senior-level output.*
- **logo**：concept 3f —— 中心紫色节点压金色 **M** 字标（渐变+辉光，谷底下拍点），四周 12 个金/紫芒点用细线连成 AI 神经网络，主光束带数据流点。正式资产已落 `maestro/webui/static/maestro-mark.svg`（完整）+ `maestro-mark-sm.svg`（简化版，侧边栏/favicon）；探索草稿 concepts 已删。

引流策略：组合 funnel = 公众号沉淀 + 私人微信高粘；受众重心 = 中文开发者。本 epic 落地第一个触点（WebUI 关于页），并把 logo 正式接入产品。

---

## 任务 1：logo 资产落地 + 接入 WebUI

### Functional design（用户体验）

- concept 3f 成为 Maestro 正式视觉标识。
- WebUI 侧边栏左上角的占位圆点（`.brand-dot`）换成 logo。
- 浏览器标签页出现 favicon。
- 关于页顶部 hero 使用完整 logo。

> 注：侧边栏页脚维护者署名「由 挖宝的瓦力 出品 →」链接 `/about`，**挪到任务 2** 实现——`/about` 路由在任务 2 才存在，放任务 1 会产生死链，违反闭环规则。

### Technical design

**资产文件**（已由 orchestrator 产出落在 `maestro/webui/static/`，coder 不需重新生成，只做接入）：

- `maestro-mark.svg` —— 完整 3f，用于关于页 hero（及未来 README）。已移除固定 `width`/`height` 仅留 `viewBox`；`<defs>` id 加 `mark-` 前缀，规避与总览页 sparkline（`id="sparkGrad"` 等）的 id 碰撞。
- `maestro-mark-sm.svg` —— 简化版：只保留中心 M-in-node（去掉外圈光芒/网络/数据流点），16–32px 下清晰，兼作 favicon；id 加 `marksm-` 前缀。

**`_base.html`**：
- 侧边栏 `<div class="brand-dot"></div>` → `<img class="brand-logo" src="/static/maestro-mark-sm.svg" alt="Maestro" width="28" height="28">`。
- `<head>` 加 `<link rel="icon" type="image/svg+xml" href="/static/maestro-mark-sm.svg">`。

**`maestro.css`**：
- 新增 `.brand-logo`（尺寸/对齐）；logo 由 12px 占位点变 28px，`.brand-sub` 的 `padding-left` 需从 `30px` 调到约 `46px` 以保持版本号对齐。
- 删除已无引用的 `.brand-dot` 规则。
- logo 自带品牌色（金/紫），**不改** `--accent`（色彩张力已定：保留品牌色）。

**`docs/branding/`** 整理：
- 新增 `docs/branding/README.md` 品牌指南：palette（墨黑 `#1E293B` / 金 `#F59E0B`+`#FDE68A` / 紫 `#7C3AED`+`#A78BFA`/`#6D28D9`）、logo 文件清单与用法、slogan、do/don't。
- 定稿资产保留；草稿 `concepts/`（未选中的 bold-1/2/3、3b/3c/3d/3e、各 preview*.html、第一版 concept-1/2/3）整理删除——**删除前列清单、等维护者确认（H4）**。

### Failure modes

- SVG id 碰撞 → 已用前缀规避；接入后目视确认侧边栏/关于页 logo 与 sparkline 渐变都正常。
- 简化 mark 在 favicon 尺寸糊 → 简化版只剩 M-in-node，已为此设计。
- 浏览器不支持 svg favicon（极旧）→ 退化为无 favicon，不影响功能。

---

## 任务 2：WebUI 关于页 `/about`

### Functional design（用户体验）

侧边栏 nav 末位新增「关于」；侧边栏页脚常驻维护者署名「由 挖宝的瓦力 出品」链接 `/about`（首页及所有页可见，兼作 funnel 入口）。`/about` 页自上而下四区块：

1. **项目简介**：logo + wordmark「Maestro」+ slogan 主/副句 + 一句话介绍。
2. **公众号**：二维码（`qr-wechat-mp.jpg`）+ 名称「挖宝的瓦力」+「扫码关注，获取 AI 协作方法论与更新」。
3. **私人微信**：二维码（`qr-wechat-personal.jpg`）+「挖宝的瓦力」+「扫码加我，直接提建议」。
4. **GitHub 反馈**：链接到 `https://github.com/kmeng/maestro/issues`，「去 GitHub 提 issue / Star ⭐」。

### Technical design

**新增 `maestro/webui/about_view.py`**（与 `savings_view` 等同构）：

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    from maestro.webui import templates  # 延迟 import，避免 templates 子目录名碰撞
    return templates.TemplateResponse(request, "about.html", {})
```

**`__init__.py`**：在 templates 绑定后的延迟 import 区块（现 line 42–52）加入 `about_view` router 并 `include_router`——与 history/live/overview/problem/savings 同一处理，保证 `from maestro.webui import templates` 晚解析。

**新增 `templates/about.html`**：`{% extends "_base.html" %}`、`{% set nav_active = "about" %}`、`{% block title %}关于{% endblock %}`。四区块用既有 `.panel` 等 token 类。二维码 `<img class="qr-img">`。

**`_base.html`**：
- nav 末位加：
```html
<a href="/about" class="{% if nav_active == 'about' %}active{% endif %}" {% if nav_active == 'about' %}aria-current="page"{% endif %}>关于</a>
```
- 侧边栏页脚 `.sb-footer` 前加维护者署名：
```html
<div class="sb-maker">由 <a href="/about">挖宝的瓦力</a> 出品</div>
```

**`maestro.css`**：
- 关于页区块布局 + `.qr-img`。两张二维码源尺寸不同（mp 28KB / personal 63KB），用 `.qr-img { width: 200px; height: 200px; object-fit: contain; }` 统一显示。
- `.sb-maker`（小号、muted、链接走 `--accent`）。
- 用既有 design tokens（ADR-0012），不引入新 CSS 文件。

### Failure modes

- 二维码图片缺失 → `<img>` 显示 alt 文本（「公众号二维码 · 挖宝的瓦力」），页面不崩。
- 现有页面回归：nav 多一项——核对是否有测试断言 nav 精确内容（实现前 grep `tests/webui/`）。

---

---

## 后续触点（拉新）— #135 / #136（2026-05-23 纳入，随 v1.0.1 发布）

WebUI funnel（任务 1/2）触达的是**已安装并运行 Maestro 的用户**（留存/转化）。拉新靠 GitHub 入口，故补两个触点：

### #135 README 品牌头 + 社区区（README.md / README.zh-CN.md）
- **顶部品牌头**：居中 logo（`maestro/webui/static/maestro-mark.svg`，`<img width="120">`）+ `# Maestro` + slogan（英文版 *You conduct. The AI plays.* / 中文版「你来指挥，AI 来演奏」）+ 5 个 badge（Release 动态 / MIT / Python 3.10+ / Built with Claude Code / Self-built by AI→BUILD_LOG.md）+ 语言切换，外包 `<div align="center">`。
- **社区区**（Contributing 之后、License 之前）：公众号 + 私人微信二维码（`<img width="180">`）+「挖宝的瓦力」+ GitHub Issues 链接。两份 README 对齐。
- H3：README 改动的专属 issue=#135（维护者明确指示）。文档由 orchestrator 直接撰写（markdown 文档，内容经维护者逐字确认）。

### #136 release-notes.md 社区页脚
- 仓库根 `release-notes.md`（release.yml 在 tag 时 `--notes-file` 读取）末尾加「社区 / Community」页脚：文字 + 指向 README 社区区（`#community--contact`）与 GitHub Issues。release notes 不嵌本地图。

## 不在范围内

- 后端表单 / 留言收集（关于页纯静态展示）。
- CLI 引流触点（后续可挂本 epic）。
- 改 WebUI `--accent` 主题色 / ADR-0012（保留品牌色，已定）。

## 任务拆分（各一个本地分支，merge 进 v1.1；先失败测试后实现）

| 任务 | 范围文件 | 估时 |
| --- | --- | --- |
| 1 logo 资产 + 接入 | `static/maestro-mark*.svg`(新)、`_base.html`、`maestro.css`、`docs/branding/`(新) | ~1.5h |
| 2 关于页 | `about_view.py`(新)、`templates/about.html`(新)、`__init__.py`、`_base.html`、`maestro.css`、`tests/webui/test_about_view.py`(新) | ~2h |

两任务都改 `_base.html`（任务 1 改 brand + favicon，任务 2 加 nav 项），文件不互斥 → **串行**：先 1 后 2。

## Test plan

- **任务 1**：单元（`tests/test_webui_base_template.py` 扩展）——`_base.html` 渲染含 `maestro-mark-sm.svg`（侧边栏 logo）+ `class="brand-logo"` + head favicon link。Smoke——浏览器看侧边栏 logo + 标签页 favicon，确认 sparkline 渐变未被 id 碰撞破坏。
- **任务 2**（`tests/test_webui_about_view.py` 新增）：`GET /about` → 200；响应含 slogan 文本「你来指挥，AI 来演奏」；含两个二维码 `src`（`qr-wechat-mp.jpg` / `qr-wechat-personal.jpg`）；含 GitHub issues 链接；`aria-current="page"` 落在「关于」。`_base.html` 扩展断言含 `.sb-maker` + 「挖宝的瓦力」+ `/about` 链接。Smoke——访问 /about 两码尺寸一致、nav 高亮、署名可点、GitHub 链接可点、其它页无回归。

## 决定（2026-05-23 维护者拍板）

1. **色彩张力**：保留 logo 金/紫品牌色，不动 WebUI `--accent` 蓝（ADR-0012 不受影响）。
2. **nav「关于」位置**：nav 末位。
3. **维护者署名**：侧边栏页脚加「由 挖宝的瓦力 出品 →」链接 `/about`（首页及所有页可见，兼作 funnel 入口）。
4. **二维码统一显示尺寸**：200×200 `object-fit: contain`。
