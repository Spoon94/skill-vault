[English](./INSTALL.md) | [中文](./INSTALL.zh.md)

# Installing skills (instructions for agents)

This file is for **agents**. Humans get the overview from the README; agents follow this file to install skills on the target platform.

## Key rules

1. **Confirm the target platform first.** When the user has not specified it, ask once, or infer it from the current environment (see the table below).
2. **Install only the skills that are needed**; do not copy everything. When the user names specific skills, install only those.
3. **Keep directories intact.** Each skill is a directory that holds `SKILL.md` and the resources it uses.
   Copy the directory as a whole; never copy just `SKILL.md`.
4. **Verify after installing.** Confirm that the symlink or directory exists and that `SKILL.md` is readable.

## Platforms and install directories

| Platform | Install directory | How to detect |
|------|----------|----------|
| Claude Code | `~/.claude/skills/` | A `claude` command exists in the environment |
| Codex CLI | `~/.codex/skills/` | A `codex` command exists in the environment |
| Copilot CLI | `~/.agents/skills/` | A `copilot` command exists in the environment |
| OpenCode | `~/.opencode/skills/` | An `opencode` command exists in the environment |
| Gemini CLI | Supports `SKILL.md`; `~/.gemini/skills/` or `.gemini/skills/` inside a project | A `gemini` command exists in the environment |

## Option 1: copy a single skill (general)

```bash
# 1. Get the repository (skip if already cloned)
git clone https://github.com/Spoon94/skill-vault.git
cd skill-vault

# 2. Copy the target skill to the platform directory (Claude Code + git-commit as an example)
mkdir -p ~/.claude/skills
cp -r git-commit ~/.claude/skills/
```

## Option 2: symlink (recommended, so the skill follows repository updates)

```bash
# Leave the repository where it is and symlink it into the platform directory
ln -sfn "$PWD/git-commit" ~/.claude/skills/git-commit
```

The benefit of a symlink: after `git pull` the skill is automatically up to date. If the target platform does not support symlinks, use option 1.

## Option 3: bulk installation

```bash
# The official skills CLI installs from a remote repository
npx skills add https://github.com/Spoon94/skill-vault
```

## Which skills to install

When the user only says "install XX", install by name. When the user asks "what is there" or lets you choose, read the "Skill index" in `README.md` — it lists all the skills by scenario together with what each one is for.

**Nested paths**: some skills live under category directories; use the full relative path when copying:

```bash
cp -r superpowers/brainstorming        ~/.claude/skills/
cp -r anthropics/skills/docx           ~/.claude/skills/
cp -r obsidian/obsidian-markdown       ~/.claude/skills/
cp -r diagram/diagram-mermaid          ~/.claude/skills/
```

Top-level skills (`git-commit`, `gh`, `tavily`, `eli5`, `clarify`, etc.) use the directory name directly.

## Verify the installation

```bash
# The directory exists and SKILL.md is readable
ls ~/.claude/skills/<name>/SKILL.md
```

In Claude Code, start a new session: skills trigger automatically by their `description`, or are invoked explicitly with `/<name>`.

## Notes

- `anthropics/template` is a scaffold template, not a usable skill; do not install it.
- This repository has no plugin-marketplace metadata (it is not a `.claude-plugin` package). It is distributed by **copying directories**.
