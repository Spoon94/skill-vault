# 安装 skill（给 agent 的指令）

本文件面向 **agent**。人在 README 看简介；agent 按本文件把 skill 装到目标平台。

## 关键规则

1. **先确认目标平台**。用户没指定时，问一次，或用当前环境判断（见下表）。
2. **只装需要的 skill**，不要全量拷贝。用户指定名字时，只装那些。
3. **保留目录完整性**。每个 skill 是一个目录，目录里有 `SKILL.md` 和它用到的资源。
   拷贝时整个目录一起拷，不要只拷 `SKILL.md`。
4. **装完验证**。确认软链或目录存在，且 `SKILL.md` 可读。

## 平台与安装目录

| 平台 | 安装目录 | 判断依据 |
|------|----------|----------|
| Claude Code | `~/.claude/skills/` | 环境有 `claude` 命令 |
| Codex CLI | `~/.codex/skills/` | 环境有 `codex` 命令 |
| Copilot CLI | `~/.agents/skills/` | 环境有 `copilot` 命令 |
| OpenCode | `~/.opencode/skills/` | 环境有 `opencode` 命令 |
| Gemini CLI | 参考各 skill 目录下的 `GEMINI.md` | 环境有 `gemini` 命令 |

## 方式一：拷贝单个 skill（通用）

```bash
# 1. 取仓库（已克隆则跳过）
git clone https://github.com/Spoon94/skill-vault.git
cd skill-vault

# 2. 拷贝目标 skill 到平台目录（以 Claude Code + git-commit 为例）
mkdir -p ~/.claude/skills
cp -r git-commit ~/.claude/skills/
```

## 方式二：软链（推荐，便于随仓库更新）

```bash
# 仓库留在原处，软链到平台目录
ln -sfn "$PWD/git-commit" ~/.claude/skills/git-commit
```

软链的好处：`git pull` 后 skill 自动是最新版。若目标平台不支持软链，用方式一。

## 方式三：批量安装

```bash
# 官方 skills CLI 从远程仓库装
npx skills add https://github.com/Spoon94/skill-vault
```

## 装哪些 skill

用户只说「装 XX」时，按名字装。用户说「有什么」或让你挑时，读 `README.md` 的
「技能索引」——那里按场景列了全部技能与各自用途。

**嵌套路径注意**：部分 skill 在分类目录下，拷贝时用完整相对路径：

```bash
cp -r superpowers/brainstorming        ~/.claude/skills/
cp -r anthropics/skills/docx           ~/.claude/skills/
cp -r obsidian/obsidian-markdown       ~/.claude/skills/
cp -r diagram/diagram-mermaid          ~/.claude/skills/
```

顶层 skill（`git-commit`、`gh`、`tavily`、`eli5`、`clarify` 等）直接用目录名。

## 验证安装

```bash
# 目录存在，且 SKILL.md 可读
ls ~/.claude/skills/<name>/SKILL.md
```

Claude Code 里新开会话，skill 按 `description` 自动触发，或用 `/<name>` 显式调用。

## 注意

- `anthropics/template` 是脚手架模板，不是可用技能，不要装。
- 本仓库无插件市场元数据（不是 `.claude-plugin` 包）。分发方式是**拷贝目录**。
