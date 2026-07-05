# Diagram Skill Family

4 个独立 Agent Skills，按输出格式分工，覆盖产品/技术画图的全场景需求。

| Skill | 输出形态 | 主用途 | 必需依赖 |
|---|---|---|---|
| [`diagram-mermaid`](diagram-mermaid/) | Mermaid 代码块（内联 Markdown） | GitHub README/issue/PR 嵌入，零依赖 | 无 |
| [`diagram-plantuml`](diagram-plantuml/) | PlantUML 代码块（内联 Markdown） | UML/云架构/网络拓扑/安全/ArchiMate/BPMN/数据管道/IoT 等专业图 | 无（Java + plantuml.jar 可选） |
| [`diagram-html`](diagram-html/) | 独立 HTML 文件 | 可分享的成品图，浏览器打开即用，双主题切换 + 浏览器导出菜单 | 无（Node.js 可选） |
| [`diagram-image`](diagram-image/) | SVG + PNG 文件 | 命令行直接产出图片文件，适合 CI/批处理/嵌入不支持 SVG 的环境 | Python 3（cairosvg/rsvg/puppeteer 可选） |

## 选用决策树

```
用户说"画个图" →
├─ 看输出场景
│   ├─ 在 Markdown/README/issue 里嵌入（要源码可读、可 diff） → 代码块路线
│   │   ├─ 基础图（流程/时序/状态/ER/思维导图/Gantt/饼图/时间线/git图/用户旅程）
│   │   │   → diagram-mermaid（零依赖，GitHub 直接渲染）
│   │   └─ UML/云架构/网络拓扑/安全/ArchiMate/BPMN/数据管道/IoT
│   │       → diagram-plantuml（专业图标库 9500+）
│   │
│   └─ 要独立文件分享 → 文件路线
│       ├─ 要可交互的成品（双主题切换、点按钮导出、可分享给非技术同事）
│       │   → diagram-html（archify，HTML 文件 + 浏览器导出菜单）
│       └─ 要命令行直接产出图片文件（CI/批处理/嵌入不支持 SVG 的环境）
│           → diagram-image（fireworks，SVG + PNG 文件）
│
└─ 用户明确指定格式 → 直接走对应 skill
```

### 默认推荐（用户没明说时）

- **"画个流程图/时序图"** → `diagram-mermaid`（最轻量，零依赖，GitHub 渲染）
- **"画个 AWS 云架构"** → `diagram-plantuml`（云图标库）
- **"画个 SaaS 架构图，能分享出去"** → `diagram-html`（HTML 可分享）
- **"出个 SVG/PNG 文件给我"** → `diagram-image`（命令行出文件）

## 各 skill 详细说明

### diagram-mermaid

11 种 Mermaid 图类型：flowchart / sequence / class / state / ER / Gantt / pie / mindmap / timeline / gitGraph / journey。

- **零依赖**：生成的代码块直接在 GitHub/Obsidian/VS Code 渲染
- **结构**：`SKILL.md` + `references/` (3 个深度文档) + `examples/` (11 个标准示例)
- **来源**：全新创建

### diagram-plantuml

9 大专业图领域：UML / Cloud (AWS/Azure/GCP/Alibaba/IBM/OpenStack/K8s) / Network / Security / ArchiMate / BPMN / Data Analytics / IoT / Mindmap。

- **9500+ mxgraph 图标**：覆盖 AWS/Azure/GCP/Cisco 等主流云厂商和网络设备
- **结构**：`SKILL.md` + `references/` (9 个领域文档) + `stencils/` (61 个图标索引) + `examples/` (9 个领域子目录)
- **来源**：合并自 markdown-viewer/skills 的 9 个 PlantUML 子技能

### diagram-html

5 种图类型：architecture / workflow / sequence / data flow / lifecycle。

- **双主题切换**：暗/亮主题，按 T 键切换，跟随系统 prefers-color-scheme
- **导出菜单**：按 E 键打开，复制 PNG 到剪贴板，下载 PNG/JPEG/WebP/SVG（4× 分辨率）
- **结构**：`SKILL.md` + `bin/` + `renderers/` (5 个图类型渲染器) + `schemas/` (6 个 JSON schema) + `scripts/` + `examples/` + `assets/`
- **来源**：导入自 archify v2.10（基于 Cocoon-AI/architecture-diagram-generator v1.0 演化）

### diagram-image

10 种图模板：architecture / sequence / flowchart / ER / state / use-case / data-flow / timeline / comparison / agent-architecture。

- **8 种视觉风格**：flat-icon / dark-terminal / blueprint / notion-clean / glassmorphism / claude-official / openai / dark-luxury
- **命令行产出**：`scripts/generate-from-template.py` + `validate-svg.sh` + `cairosvg` 导出 PNG
- **结构**：`SKILL.md` + `scripts/` (4 个) + `templates/` (10 个 SVG 模板) + `references/` (8 种风格 + icons + 布局最佳实践) + `assets/samples/` + `fixtures/`
- **来源**：导入自 fireworks-tech-graph v1.0.4

## diagram-html vs diagram-image 的关键区别

虽然 archify（diagram-html）也能通过浏览器手动导出 PNG，但与 fireworks（diagram-image）定位不同：

| 维度 | diagram-html (archify) | diagram-image (fireworks) |
|---|---|---|
| 主输出 | HTML 文件 | SVG/PNG 文件 |
| 图片生成方式 | 浏览器打开 HTML → 点导出菜单按钮 → 下载 | 命令行脚本直接产出文件 |
| 是否需要浏览器 | 需要（手动点击导出） | 不需要（脚本直接出文件） |
| 是否可自动化 | 否（需要人工点击） | 是（CI/CD、批处理可调用） |
| 主题/风格 | 暗+亮双主题 + 双主题 SVG | 8 种风格 |
| 图类型 | 5 种 | 10 种 |
| 接受 Mermaid 输入 | 是 | 否 |

**不重叠的部分**：
- diagram-html 独有：双主题切换、HTML 内导出菜单、复制到剪贴板、Mermaid 输入转换
- diagram-image 独有：命令行直接出文件、8 种视觉风格、ER/use-case/timeline/comparison/agent-architecture 5 种额外图类型

## 安装

把 4 个 skill 目录复制到对应平台的 skills 目录：

| 平台 | 安装目录 |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex CLI | `~/.codex/skills/` |
| Copilot CLI | `~/.agents/skills/` |
| OpenCode | `~/.opencode/skills/` |

例如，安装到 Claude Code：

```bash
cp -r diagram-mermaid diagram-plantuml diagram-html diagram-image ~/.claude/skills/
```

## 设计文档

完整的方案设计（包括 4 个 skill 的选型理由、对比、路由决策、错误处理、测试方案）见：

[`/Users/spoon/Code/arch-diagram/docs/specs/2026-07-05-diagram-skill-family-design.md`](../docs/specs/2026-07-05-diagram-skill-family-design.md)

## 来源项目

| Skill | 来源项目 | 版本 | 上游 |
|---|---|---|---|
| diagram-mermaid | —（全新创建） | — | — |
| diagram-plantuml | markdown-viewer/skills (9 个 PlantUML 子技能合并) | — | https://github.com/markdown-viewer/skills |
| diagram-html | archify | v2.10 | https://github.com/tt-a1i/archify (基于 Cocoon-AI/architecture-diagram-generator v1.0) |
| diagram-image | fireworks-tech-graph | v1.0.4 | https://github.com/yizhiyanhua-ai/fireworks-tech-graph |

## License

各 skill 沿用其来源项目的 license（archify 和 fireworks-tech-graph 均为 MIT）。diagram-mermaid 为新建，无 license 限制。
