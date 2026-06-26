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

### 独立技能

| 技能 | 描述 |
|------|------|
| [conventional-commits](./conventional-commits) | 规范 Git 提交消息格式，便于自动化生成版本号和变更日志；macOS 下可自动 `pbcopy` 到剪贴板 |
| [gh](./gh) | GitHub CLI（`gh`）调用模式：结构化输出、分页、仓库定位、搜索 vs 列表、`gh api` 兜底 |
| [tmux](./tmux) | 以脚本方式驱动 tmux：后台会话、`send-keys`、`capture-pane`，自动化 REPL/SSH/调试器 |
| [semble](./semble) | 用 `semble search` 替代 grep+read 做语义代码检索，省 ~98% token |
| [mcp2cli](./mcp2cli) | 把任意 MCP 服务器、OpenAPI 规范或 GraphQL 端点变成 CLI，无需代码生成 |
| [worktrunk](./worktrunk) | Worktrunk（`wt` CLI）使用指南：git worktree 管理、hooks 和配置 |
| [engram-mem](./engram-mem) | 基于本地 engram CLI(SQLite + FTS5)的跨会话持久记忆,工作与生活通用,支持决策、偏好、计划等记忆的存取与检索 |
| [deslop-bi](./deslop-bi) | 双语去 AI 味：识别并修复中英文文本中的 AI 生成痕迹——浮夸修辞、套路结构、机器翻译腔、"深入探讨/打造/赋能"等中文 AI 高频词 |

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

为保证开箱可用，仅做了一处路径引用修改：

- `superpowers/brainstorming/SKILL.md` 中的 `skills/brainstorming/visual-companion.md` → `visual-companion.md`

其余所有内容与各上游项目保持一致。

## 贡献

欢迎 PR 和 Issue：

- 新增 skill：请放在对应分类目录下，并在本 README 表格中追加一行
- 修复/改进现有 skill：建议先在 Issue 中讨论后再提 PR
- 提交规范：遵循 [Conventional Commits](./conventional-commits)

## License

[MIT](./LICENSE)
