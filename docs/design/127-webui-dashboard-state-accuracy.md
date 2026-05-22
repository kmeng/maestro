# Design: WebUI 仪表盘反映已有配置状态

**Status**: approved (2026-05-23)
**Issue**: #127 (epic)
**Related**: `maestro/webui/overview_api.py`, `maestro/webui/index.html`, `maestro/webui/scaffold_view.py`, `maestro/webui/templates/scaffold_picker.html`, `maestro/registry/projects.py`, `maestro/team/io.py`
**ADR**: 不需要。两处改动都是既有接口的**加性**扩展——`/api/overview` 响应新增一个字段（向后兼容，且该 API 只被自带前端消费，非对外契约）；脚手架页读取既有注册表渲染。无新依赖、无新存储格式、无新角色。

## 背景

WebUI 实测发现：总览页与脚手架页**只反映派发活动，不反映已有配置**。底层数据（`team.yaml`、`~/.maestro/projects.json`）都已落地，视图层却没读，导致已配团队 / 已应用过 Maestro 的用户看到的仍是「初次使用」界面。

侧边栏版本号（`0.1.0`）按现状正确（这是最近发布版，`v1.0` 只是开发分支名），**本设计不含版本号修改**——延后到这些修复全部完成、测试通过、正式发布时再 bump。届时一并把 `version` 注入改成 Jinja 全局（当前只有 index 路由传 `version`，其余页侧边栏版本为空）。

---

## 任务 A：总览「当前运行」感知团队配置状态

### 问题

`index.html` 的「当前运行」面板用 `data.cumulative.dispatches === 0` 判断是否显示「开始 → 配置团队」引导按钮（`index.html:208`）。`/api/overview`（`overview_api.py`）完全基于 dispatch 日志，**不读团队配置**。因此「已配团队但尚未派发」被错判为「未配置团队」。

### Functional design（用户体验）

「当前运行」面板按**团队配置状态**而非派发次数决定显示：

| 团队状态 | 面板显示 |
| --- | --- |
| 未配置（`team.yaml` 不存在） | 「开始 → 配置团队」引导按钮（链接 `/wizard`），meta 空 |
| 配置损坏（`team.yaml` 存在但无法解析/校验失败） | 「团队配置有误 → 去修复」链接（链接 `/team`），meta 空 |
| 已配置 + 无运行中调度 | 「暂无运行中的调度。」，meta「空闲」 |
| 已配置 + 有运行中调度 | 现状的运行卡片（role · summary / model · member） |

「初次运行」副标题（`index.html:122`，基于 `dispatches === 0`）保持不变——它表达的是「尚无派发遥测」，语义独立，不在本任务范围。

### Technical design

**`overview_api.py`** — `get_overview()` 响应新增 `team` 字段：

```python
"team": {"status": "configured" | "absent" | "invalid"}
```

新增私有 helper，复用 `team_api._project_root()` 的同一约定（webui 运行目录即项目，`Path.cwd()`）：

```python
def _team_status() -> str:
    """Return 'configured' | 'absent' | 'invalid' for the cwd project's team.yaml.

    NEVER raises — the dashboard must render even if team-config resolution
    fails. Maps load_team_config's three-state result; any unexpected
    exception degrades to 'invalid' (signals "something's off", never
    re-onboards a configured user).
    """
    try:
        result = load_team_config(Path.cwd())
    except Exception:
        return "invalid"
    if result is None:
        return "absent"
    if isinstance(result, TeamConfig):
        return "configured"
    return "invalid"  # TeamConfigInvalid
```

`load_team_config` 上游契约（`maestro/team/io.py`，本设计写作时已核对）：
- 签名：`load_team_config(project_root: Path | str) -> TeamConfig | TeamConfigInvalid | None`
- 返回 `None` = 文件不存在；`TeamConfig` = 解析+校验通过；`TeamConfigInvalid` = 文件存在但 YAML 解析或 schema 校验失败。
- 失败契约：内部已捕获 `OSError` / `yaml.YAMLError` / `ValidationError`，**不向上抛**（返回 `TeamConfigInvalid`）。`_team_status` 的 `try/except` 仅兜底 `team_config_path()` / `.exists()` 等罕见 OS 异常。

`_empty_response()`（遥测关闭/缺失分支）也要带 `team` 字段，保持响应形状一致——遥测关闭不代表团队未配置，故此分支也调用 `_team_status()`。

**`index.html`** — 「当前运行」面板 JS 改判断：

```js
const team = data.team.status;
if (team === 'absent') {
  nowRunningBody.innerHTML = '<a href="/wizard" class="btn btn-primary">开始 → 配置团队</a>';
  nowRunningMeta.textContent = '';
} else if (team === 'invalid') {
  nowRunningBody.innerHTML = '<a href="/team" class="btn">团队配置有误 → 去修复</a>';
  nowRunningMeta.textContent = '';
} else if (data.now_running === null) {
  nowRunningBody.innerHTML = '<div class="empty-run">暂无运行中的调度。</div>';
  nowRunningMeta.textContent = '空闲';
} else {
  /* 现状运行卡片渲染，不变 */
}
```

### Failure modes

- `team.yaml` 不存在 → `absent` → 引导（正确的初次体验）。
- `team.yaml` 损坏 → `invalid` → 修复链接（不再误导去重新配置）。
- team 解析抛意外异常 → `invalid`（仪表盘不崩，不把已配用户打回初次态）。
- 遥测关闭 → 仍报真实 team 状态。

---

## 任务 B：脚手架页展示已应用项目列表

### 问题

`~/.maestro/projects.json` 每次 apply 由 `upsert_project()` 写入，`read_registry()` 能读出按 `last_opened_at` 倒序、已剔除死路径的列表。但 `/scaffold` picker（`scaffold_view.py:115` → `scaffold_picker.html`）只渲染新建/接入表单，从不读注册表。

### Functional design（用户体验）

`/scaffold` 页在表单**上方**新增「已应用的项目」区块：
- 有记录：列出每个项目的路径 + 上次打开时间，每行带「查看计划 →」链接（指向 `/scaffold/plan?path=<path>&mode=take_over`，因为对已存在项目重新过脚手架即 take_over 语义）。
- 无记录：显示「还没有在任何项目上应用过 Maestro。」占位，下面照常是表单。

### Technical design

**`scaffold_view.py`** — `picker()` 路由读注册表并传入 context：

```python
from maestro.registry.projects import read_registry

@router.get("/scaffold", response_class=HTMLResponse)
async def picker(request: Request):
    from maestro.webui import templates
    projects = [
        {
            "path": str(e.path),
            "last_opened_display": e.last_opened_at.strftime("%Y-%m-%d %H:%M UTC"),
        }
        for e in read_registry()
    ]
    return templates.TemplateResponse(
        request, "scaffold_picker.html", {"projects": projects}
    )
```

`read_registry()` 上游契约（`maestro/registry/projects.py`，已核对）：
- 签名：`read_registry() -> list[ProjectEntry]`
- `ProjectEntry`（frozen dataclass）：`path: Path`、`last_opened_at: datetime`（tz-aware UTC）。
- 失败契约：**NEVER raises**；任何异常返回空列表（或已收集的部分项）。死路径（`path.exists()` 为假）静默剔除。已按 `last_opened_at` 倒序排序。

**`scaffold_picker.html`** — 在表单 `<section>` 上方插入列表区块：

```jinja
{% if projects %}
<section class="panel" style="max-width: 720px; margin-bottom: 16px;">
  <header class="panel-h"><h2 class="panel-title">已应用的项目</h2></header>
  <ul class="proj-list">
    {% for p in projects %}
    <li class="proj-row">
      <span class="proj-path">{{ p.path }}</span>
      <span class="proj-time">{{ p.last_opened_display }}</span>
      <a class="proj-link" href="/scaffold/plan?path={{ p.path | urlencode }}&mode=take_over">查看计划 →</a>
    </li>
    {% endfor %}
  </ul>
</section>
{% else %}
<div class="page-sub">还没有在任何项目上应用过 Maestro。</div>
{% endif %}
```

样式用既有 design tokens（`var(--border)` 等，ADR-0012），不引入新 CSS 文件。

### Failure modes

- 注册表不存在 / 损坏 / 权限错 → `read_registry()` 返回 `[]` → 显示占位，表单正常。
- 路径含特殊字符 → 模板用 `urlencode` 过滤 query 注入；路径文本由 Jinja 自动 HTML 转义。

---

## 不在范围内

- 侧边栏版本号 bump（延后到发布）。
- 总览「初次运行」副标题逻辑（语义独立）。
- 脚手架 apply 流程本身、SSE 实时更新（仍是 v0.0.3 同步实现）。
- 注册表 schema / 写入逻辑改动（只读不写）。

## 任务拆分（各一个 PR，先失败测试后修复）

| 任务 | 范围文件 | 估时 |
| --- | --- | --- |
| A 总览 team 感知 | `overview_api.py`、`templates/index.html` | ~1.5h |
| B 脚手架已应用项目 | `scaffold_view.py`、`templates/scaffold_picker.html` | ~1.5h |

两任务文件集互斥，无共享上游改动，可并行成一个波次。

## Test plan

- **任务 A**：
  - Unit (`tests/test_webui_overview_api.py`)：team.yaml 不存在 → `team.status == "absent"`；有效 team.yaml → `"configured"`；损坏 team.yaml → `"invalid"`；遥测关闭分支也带 `team` 字段。
  - Smoke：起 webui，无 team.yaml 时总览显示引导；写入有效 team.yaml 后刷新显示「暂无运行中的调度」而非引导。
- **任务 B**：
  - Unit (`tests/test_webui_scaffold_redesign.py` 或新增)：注册表为空 → 渲染占位且无列表；注册表有 N 项 → 渲染 N 行且含路径与「查看计划」链接；路径经 urlencode。
  - Smoke：apply 一个项目后访问 `/scaffold`，确认它出现在列表里。
