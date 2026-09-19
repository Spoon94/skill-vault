# skill-vault

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Spoon94/skill-vault?style=social)](https://github.com/Spoon94/skill-vault)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Spec-blue)](https://agentskills.io/specification)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#贡献)

> 个人收藏并整理的 AI 编程助手 **Agent Skills** 集合，按来源/主题分类组织，开箱即用。

每个 skill 都是一个独立目录，包含 `SKILL.md` 与相关资源，遵循 [Agent Skills 规范](https://agentskills.io/specification)，可被 Claude Code、Codex CLI、Copilot CLI、Gemini CLI、OpenCode 等任何兼容 skills 的 AI 编程助手加载和调用。

## 目录

- [快速开始](#快速开始)
- [技能分类](#技能分类)
  - [superpowers/](#superpowers)
  - [anthropics/](#anthropics)
  - [obsidian/](#obsidian)
  - [diagram/](#diagram)
  - [独立技能](#独立技能)
- [安装方式](#安装方式)
- [与上游项目的差异](#与上游项目的差异)
- [贡献](#贡献)
- [License](#license)

## 快速开始

以 Claude Code 为例，安装单个 skill：

```bash
# 1. 克隆本仓库
git clone https://github.com/Spoon94/skill-vault.git
cd skill-vault

# 2. 把需要的 skill 拷贝到 Claude Code 的 skills 目录
mkdir -p ~/.claude/skills
cp -r superpowers/test-driven-development ~/.claude/skills/

# 3. 在 Claude Code 中即可通过 /test-driven-development 调用
```

批量安装（推荐）：

```bash
# 使用官方 skills CLI 从远程仓库安装
npx skills add https://github.com/Spoon94/skill-vault
```

## 技能分类

### [superpowers/](./superpowers)

基于 [obra/superpowers](https://github.com/obra/superpowers) 拆分的开发流程类技能，覆盖从需求探索到分支收尾的完整研发链路。

| 技能 | 描述 |
|------|------|
| [brainstorming](./superpowers/brainstorming) | 创建前的设计探索和需求澄清 |
| [systematic-debugging](./superpowers/systematic-debugging) | 系统化调试方法 |
| [test-driven-development](./superpowers/test-driven-development) | 测试驱动开发 |
| [writing-skills](./superpowers/writing-skills) | 编写 skills 的最佳实践 |
| [writing-plans](./superpowers/writing-plans) | 编写实施计划 |
| [executing-plans](./superpowers/executing-plans) | 执行计划 |
| [requesting-code-review](./superpowers/requesting-code-review) | 请求代码审查 |
| [receiving-code-review](./superpowers/receiving-code-review) | 接收代码审查反馈 |
| [finishing-a-development-branch](./superpowers/finishing-a-development-branch) | 完成开发分支 |
| [dispatching-parallel-agents](./superpowers/dispatching-parallel-agents) | 分发并行代理 |
| [subagent-driven-development](./superpowers/subagent-driven-development) | 子代理驱动开发 |
| [using-git-worktrees](./superpowers/using-git-worktrees) | 使用 Git worktrees |
| [using-superpowers](./superpowers/using-superpowers) | superpowers 使用简介 |
| [verification-before-completion](./superpowers/verification-before-completion) | 完成前验证 |
| [diagnosing-superpowers](./superpowers/diagnosing-superpowers) | 复盘诊断出问题的 superpowers 会话：重复劳动、忽略计划、效果差、成本高，并生成给维护者的 bug report |

### [anthropics/](./anthropics)

来自 [anthropics/skills](https://github.com/anthropics/skills) 官方仓库的示例技能，覆盖创意设计、开发工具、企业沟通和文档处理。

| 技能 | 描述 |
|------|------|
| [algorithmic-art](./anthropics/skills/algorithmic-art) | 算法艺术创作 |
| [brand-guidelines](./anthropics/skills/brand-guidelines) | 品牌指南应用 |
| [canvas-design](./anthropics/skills/canvas-design) | Canvas 设计 |
| [claude-api](./anthropics/skills/claude-api) | 构建、调试和优化 Claude API / Anthropic SDK 应用 |
| [doc-coauthoring](./anthropics/skills/doc-coauthoring) | 文档协同写作 |
| [docx](./anthropics/skills/docx) / [pdf](./anthropics/skills/pdf) / [pptx](./anthropics/skills/pptx) / [xlsx](./anthropics/skills/xlsx) | Office 文档（Word/PDF/PPT/Excel）的创建与编辑 |
| [frontend-design](./anthropics/skills/frontend-design) | 前端设计 |
| [internal-comms](./anthropics/skills/internal-comms) | 企业内部沟通 |
| [mcp-builder](./anthropics/skills/mcp-builder) | MCP 服务器构建 |
| [skill-creator](./anthropics/skills/skill-creator) | 技能创建助手 |
| [slack-gif-creator](./anthropics/skills/slack-gif-creator) | Slack GIF 制作 |
| [theme-factory](./anthropics/skills/theme-factory) | 主题生成 |
| [web-artifacts-builder](./anthropics/skills/web-artifacts-builder) | Web Artifacts 构建 |
| [webapp-testing](./anthropics/skills/webapp-testing) | Web 应用测试 |

### [obsidian/](./obsidian)

来自 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) 的 Obsidian 相关技能。

| 技能 | 描述 |
|------|------|
| [obsidian-markdown](./obsidian/obsidian-markdown) | 创建和编辑 Obsidian Flavored Markdown（wikilinks、嵌入、callouts、properties 等） |
| [obsidian-bases](./obsidian/obsidian-bases) | 创建和编辑 Obsidian Bases（`.base`）：视图、过滤器、公式、汇总 |
| [json-canvas](./obsidian/json-canvas) | 创建和编辑 JSON Canvas（`.canvas`）文件：节点、连线、分组 |
| [obsidian-cli](./obsidian/obsidian-cli) | 通过 Obsidian CLI 操作 vault，包括插件和主题开发 |
| [defuddle](./obsidian/defuddle) | 使用 Defuddle 从网页提取干净 Markdown，节省 token |
| [knap](./obsidian/knap) | 用 Knap CLI 从模板和结构化数据（JSON/CSV）渲染 Markdown，批量生成笔记或格式化 Defuddle 输出 |

### [diagram/](./diagram)

绘图技能家族，按输出格式分工，覆盖产品/技术画图全场景。详见 [diagram/README.md](./diagram/README.md)。

| 技能 | 输出形态 | 主用途 |
|------|---------|--------|
| [diagram-mermaid](./diagram/diagram-mermaid) | Mermaid 代码块（内联 Markdown） | GitHub README/issue/PR 嵌入，零依赖，GitHub 直接渲染 |
| [diagram-plantuml](./diagram/diagram-plantuml) | PlantUML 代码块（内联 Markdown） | UML/云架构/网络拓扑/安全/ArchiMate/BPMN/数据管道等专业图（图标库 9500+） |
| [diagram-html](./diagram/diagram-html) | 独立 HTML 文件 | 可分享的成品图，浏览器打开即用，双主题切换 + 一键导出 PNG/JPEG/WebP/SVG |
| [diagram-image](./diagram/diagram-image) | SVG + PNG 文件 | 命令行直接产出图片文件，适合 CI/批处理/嵌入不支持 SVG 的环境 |
| [diagram-graphviz](./diagram/diagram-graphviz) | DOT 代码块（内联 Markdown） | 依赖树/调用图/包层级，需细粒度边路由的图，自动布局 |
| [diagram-infocard](./diagram/diagram-infocard) | HTML/CSS 卡片（直接内嵌 Markdown） | 编辑风信息卡片：知识摘要/数据高亮/公告，杂志级排版 |
| [diagram-infographic](./diagram/diagram-infographic) | 模板化信息图（空格分隔 KV 语法） | KPI 看板/时间线/路线图/SWOT/漏斗/对比/组织树，58 个内置模板 |

### 独立技能

| 技能 | 描述 |
|------|------|
| [git-commit](./git-commit) | 规范 Git 提交消息格式，便于自动化生成版本号和变更日志；macOS 下可自动 `pbcopy` 到剪贴板 |
| [gh](./gh) | GitHub CLI（`gh`）调用模式：结构化输出、分页、仓库定位、搜索 vs 列表、`gh api` 兜底 |
| [tmux](./tmux) | 以脚本方式驱动 tmux：后台会话、`send-keys`、`capture-pane`，自动化 REPL/SSH/调试器 |
| [semble](./semble) | 用 `semble search` 替代 grep+read 做语义代码检索，省 ~98% token |
| [mcp2cli](./mcp2cli) | 把任意 MCP 服务器、OpenAPI 规范或 GraphQL 端点变成 CLI，无需代码生成 |
| [worktrunk](./worktrunk) | Worktrunk（`wt` CLI）使用指南：git worktree 管理、hooks 和配置 |
| [engram-mem](./engram-mem) | 基于本地 engram CLI(SQLite + FTS5)的跨会话持久记忆,工作与生活通用,支持决策、偏好、计划等记忆的存取与检索 |
| [deslop-bi](./deslop-bi) | 双语去 AI 味：识别并修复中英文文本中的 AI 生成痕迹——浮夸修辞、套路结构、机器翻译腔、"深入探讨/打造/赋能"等中文 AI 高频词 |
| [tavily](./tavily) | 通过 Tavily CLI 做网页搜索、内容提取、站点爬取、URL 发现和带引用的深度研究，支持 context-isolated 模式过滤原始结果 |
| [hunk-review](./hunk-review) | 通过 Hunk daemon 与交互式 diff 审阅会话协作：检查会话结构、跳转文件/hunk、重载 diff 内容、添加内联 review 注释 |
| [opencli](./opencli) | 把任意网站/Electron 应用/外部 CLI 变成 `opencli <site> <command>` 的统一操作面，agent 可驱动真实浏览器、抓取页面、填表点击、维护站点适配器和 sitemap |
| [agentsview-cli](./agentsview-cli) | 本地 AI 会话历史查询：`agentsview` CLI 同步/搜索/恢复 Claude Code、Codex、Cursor 等会话，用量成本报告、语义检索、pg/duckdb/MCP 镜像 |
| [herdr](./herdr) | 通过 Herdr CLI 控制终端多路复用器：检查/操作 pane、tab、workspace，启动和协调 agent，读取输出，等待状态变化 |

## 安装方式

将需要的 skill 目录复制到对应平台的 skills 目录：

| 平台 | 安装目录 |
|------|----------|
| Claude Code | `~/.claude/skills/` |
| Codex CLI | `~/.codex/skills/` |
| Copilot CLI | `~/.agents/skills/` |
| OpenCode | `~/.opencode/skills/` |
| Gemini CLI | 参考各 skill 目录下的 `GEMINI.md` 配置 |

也可以使用 `npx skills add <repo-url>` 从远程仓库批量安装。

## 与上游项目的差异

为保证开箱可用，本仓库对 vendored 内容维护以下本地不变式，任何上游同步都必须保住：

| # | 不变式 | 原因 | 影响范围 |
|---|--------|------|----------|
| I1 | `description` ≤ 1024 字符，超长时存裁剪版 | pi harness 硬限制，超出报 `description exceeds 1024 characters` | `diagram/diagram-{html,mermaid,plantuml}`（上游 1219/1159/1452 字符，本地为合规裁剪版） |
| I2 | `description` 含 `:` / 引号等 YAML 特殊字符时必须加引号 | 否则 YAML 解析报 `Nested mappings are not allowed in compact mappings` | `semble/SKILL.md`（上游未加引号，本地加了） |
| I3 | 引用仓库内相对路径扁平化 | 上游用仓库内相对路径，本地目录结构扁平 | `superpowers/brainstorming/SKILL.md` 中 `skills/brainstorming/visual-companion.md` → `visual-companion.md` |
| I4 | opencli 结构不同：上游 `OpenCLI/skills/` 下 7 个子技能（opencli-usage / opencli-browser / opencli-adapter-author / opencli-sitemap-author / opencli-browser-sitemap / opencli-autofix / smart-search）合并为单个 `opencli/SKILL.md` + `opencli/references/` | 统一入口，按任务类型路由，避免 7 个 skill 全部进上下文 | `opencli/` 全目录：去掉子技能 frontmatter，`references/` 路径前缀重写为本地布局（`adapter/`、`sitemap/`、`search/`） |
| I5 | opencli 的 strategy 术语有两套（references 的上游文档层大写术语 vs 运行时的小写 tag），`SKILL.md` 需维护映射表 | 上游文档与自家 CLI 输出脱节；本地需要让 agent 能把 references 术语和 `list -f json` 实际输出对上 | `opencli/SKILL.md`「术语对照」表 |
| I6 | `diagram/` 家族跨两个上游集合：`arch-diagram/diagram/` 的 4 个 `diagram-*` + `arch-diagram/skills/`（即 markdown-viewer/skills）的 3 个改名为 `diagram-*` 的目录（`diagram-graphviz` / `diagram-infocard` / `diagram-infographic`，上游裸名 graphviz / infocard / infographic） | 同属绘图技能集中放置便于路由与发现 | `diagram/diagram-{graphviz,infocard,infographic}/` |
| I7 | diagram 家族统一用 `diagram-*` 前缀命名，与上游 `markdown-viewer/skills` 的裸名（graphviz/infocard/infographic）不同 | 家族内命名一致性优先于上游保真；便于按名字定位 | `diagram/diagram-{graphviz,infocard,infographic}/`；下次同步这 3 个时需重做改名 + 改 `name` 字段补丁 |
| I8 | `worktrunk/reference/claude-code.md` 中关于 `wt-switch-create` 的描述保留上游原文，但加了「本仓库未收录」标注 | 该 skill 已删除（用户不需要），上游文本仍提及它；标注避免 agent 误以为可用 | `worktrunk/reference/claude-code.md` |

除上述不变式外，其余内容与各上游项目保持一致。

## 贡献

欢迎 PR 和 Issue：

- 新增 skill：请放在对应分类目录下，并在本 README 表格中追加一行
- 修复/改进现有 skill：建议先在 Issue 中讨论后再提 PR
- 提交规范：遵循 [Conventional Commits](./git-commit)

## License

[MIT](./LICENSE)
