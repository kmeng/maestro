# Maestro 品牌指南

> 你来指挥，AI 来演奏 · 用初级的价，拿资深的活

本目录定义 Maestro 的视觉与文案规范。新增任何对外物料（WebUI、README、公众号、海报）前先读这里。

## Slogan

| | 中文 | English |
| --- | --- | --- |
| 主句（品牌记忆钩子） | **你来指挥，AI 来演奏** | You conduct. The AI plays. |
| 副句（成本硬证据） | **用初级的价，拿资深的活** | Pay junior prices for senior-level output. |

中文优先（受众重心是中文开发者）。英文锁版用于 GitHub 等国际场景。

## Logo

| 资产 | 用途 |
| --- | --- |
| [`maestro/webui/static/maestro-mark.svg`](../../maestro/webui/static/maestro-mark.svg) | 完整标识：中心紫色节点 + 金色 M 字标，四周金/紫芒点连成 AI 网络。用于关于页 hero、文档头图、较大展示场景。 |
| [`maestro/webui/static/maestro-mark-sm.svg`](../../maestro/webui/static/maestro-mark-sm.svg) | 简化标识：仅中心 M-in-node。用于侧边栏、favicon、头像等 ≤32px 小尺寸。 |

**含义**：M = Maestro，中心节点 = 指挥者（你）；四周芒点 = 被编排的异构 AI 团队，连线 = 协作网络，主光束上的小点 = 流动的指令。一图双关——音乐指挥家 + 技术编排器。

## 配色

| 角色 | 色值 |
| --- | --- |
| 墨黑（中性 / 文字） | `#1E293B` |
| 金（主强调：下拍点 / M / 光芒） | `#F59E0B`，亮部 `#FDE68A` |
| 紫（节点 / 网络 / AI） | `#7C3AED`，亮 `#A78BFA` / 深 `#6D28D9` |

> 注：WebUI 界面主题色 `--accent` 是蓝 `#2563EB`（ADR-0012），与 logo 的金/紫品牌色**并存**——logo 是有自身色彩的品牌标识，不改 UI 主题。

## Do / Don't

- ✅ 深底、浅底都可直接用。
- ✅ ≤32px 的场景（favicon、侧边栏、头像）用 `-sm` 简化版。
- ❌ 不拉伸 / 变形（保持等比，依赖 `viewBox` 缩放）。
- ❌ 不替换品牌配色、不给 logo 套额外背景框。
