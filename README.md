# skill-vault

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Spoon94/skill-vault?style=social)](https://github.com/Spoon94/skill-vault)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Spec-blue)](https://agentskills.io/specification)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#贡献)

> 个人收藏并整理的 AI 编程助手 **Agent Skills** 集合，按来源/主题分类组织，开箱即用。

每个 skill 都是一个独立目录，包含 `SKILL.md` 与相关资源。它遵循 [Agent Skills 规范](https://agentskills.io/specification)。Claude Code、Codex CLI、Copilot CLI、Gemini CLI、OpenCode 等任何兼容 skills 的 AI 编程助手都能加载和调用它。

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

## 技能全景

![技能全景](docs/images/skill-map.svg)

8 个场景分组，63 个技能——**从场景出发找技能**：要讲清话题、要画图、要打磨文本、要检索信息……先看图定位场景，再进对应目录看 `SKILL.md`。

## 组合使用

![组合流程](docs/images/skill-pipeline.svg)

流水线：**编排**（show-me / eli5 选讲解形式）→ **渲染**（diagram-\* 按需补图）→ **质量**（falsify 验伪）→ **语言**（clarify / deslop-bi 定风格）。独立工具技能（gh、tavily、tmux……）按需穿插任意环节。

**关键点**：

- `show-me` 自带内联 Mermaid 与聚焦 HTML——自带图够用时**不要**再叠 `diagram-*`；只有要 UML/云架构/DOT 边路由/成品文件时才升级。
- `eli5` 的产物**不要**再过 `clarify`（eli5 要生动、clarify 要平实，方向冲突）；`clarify` 与 `deslop-bi` 互斥（一个压平人味、一个恢复人味）。
- `falsify` 的对象是**论断/讲解/计划**，不是纯渲染产物（diagram-\* 只是按描述画图，没什么可证伪的）。

## 技能索引

- **[superpowers/](./superpowers)**（15 个）：[brainstorming](./superpowers/brainstorming)、[systematic-debugging](./superpowers/systematic-debugging)、[test-driven-development](./superpowers/test-driven-development)、[writing-skills](./superpowers/writing-skills)、[writing-plans](./superpowers/writing-plans)、[executing-plans](./superpowers/executing-plans)、[requesting-code-review](./superpowers/requesting-code-review)、[receiving-code-review](./superpowers/receiving-code-review)、[finishing-a-development-branch](./superpowers/finishing-a-development-branch)、[dispatching-parallel-agents](./superpowers/dispatching-parallel-agents)、[subagent-driven-development](./superpowers/subagent-driven-development)、[using-git-worktrees](./superpowers/using-git-worktrees)、[using-superpowers](./superpowers/using-superpowers)、[verification-before-completion](./superpowers/verification-before-completion)、[diagnosing-superpowers](./superpowers/diagnosing-superpowers)
- **[anthropics/](./anthropics)**（18 个）：[algorithmic-art](./anthropics/skills/algorithmic-art)、[brand-guidelines](./anthropics/skills/brand-guidelines)、[canvas-design](./anthropics/skills/canvas-design)、[claude-api](./anthropics/skills/claude-api)、[doc-coauthoring](./anthropics/skills/doc-coauthoring)、[docx](./anthropics/skills/docx)、[pdf](./anthropics/skills/pdf)、[pptx](./anthropics/skills/pptx)、[xlsx](./anthropics/skills/xlsx)、[frontend-design](./anthropics/skills/frontend-design)、[internal-comms](./anthropics/skills/internal-comms)、[mcp-builder](./anthropics/skills/mcp-builder)、[skill-creator](./anthropics/skills/skill-creator)、[slack-gif-creator](./anthropics/skills/slack-gif-creator)、[theme-factory](./anthropics/skills/theme-factory)、[web-artifacts-builder](./anthropics/skills/web-artifacts-builder)、[webapp-testing](./anthropics/skills/webapp-testing)
- **[obsidian/](./obsidian)**（6 个）：[obsidian-markdown](./obsidian/obsidian-markdown)、[obsidian-bases](./obsidian/obsidian-bases)、[json-canvas](./obsidian/json-canvas)、[obsidian-cli](./obsidian/obsidian-cli)、[defuddle](./obsidian/defuddle)、[knap](./obsidian/knap)
- **[diagram/](./diagram)**（7 个）：[diagram-mermaid](./diagram/diagram-mermaid)、[diagram-plantuml](./diagram/diagram-plantuml)、[diagram-html](./diagram/diagram-html)、[diagram-image](./diagram/diagram-image)、[diagram-graphviz](./diagram/diagram-graphviz)、[diagram-infocard](./diagram/diagram-infocard)、[diagram-infographic](./diagram/diagram-infographic)
- **解释 / 讲解类**（4 个）：[eli5](./eli5)、[show-me](./show-me)、[clarify](./clarify)、[falsify](./falsify)
- **独立技能**（13 个）：[git-commit](./git-commit)、[gh](./gh)、[tmux](./tmux)、[semble](./semble)、[mcp2cli](./mcp2cli)、[worktrunk](./worktrunk)、[engram-mem](./engram-mem)、[deslop-bi](./deslop-bi)、[tavily](./tavily)、[hunk-review](./hunk-review)、[opencli](./opencli)、[agentsview-cli](./agentsview-cli)、[herdr](./herdr)

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

- 新增 skill：请放在对应分类目录下。在本 README 表格中追加一行
- 修复/改进现有 skill：建议先在 Issue 中讨论后再提 PR
- 提交规范：遵循 [Conventional Commits](./git-commit)

## License

[MIT](./LICENSE)
