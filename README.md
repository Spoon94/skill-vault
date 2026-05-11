# skill-vault

个人常用的技能集合，基于 [superpowers](https://github.com/obra/superpowers) 项目拆分的独立 skills。

## 概述

每个 skill 可单独安装和使用，适用于 Claude Code、Copilot CLI、Gemini CLI 等 AI 编程助手。

## 包含的技能

| 技能 | 描述 |
|------|------|
| brainstorming | 创建前的设计探索和需求澄清 |
| systematic-debugging | 系统化调试方法 |
| test-driven-development | 测试驱动开发 |
| writing-skills | 编写 skills 的最佳实践 |
| writing-plans | 编写实施计划 |
| executing-plans | 执行计划 |
| requesting-code-review | 请求代码审查 |
| receiving-code-review | 接收代码审查反馈 |
| finishing-a-development-branch | 完成开发分支 |
| dispatching-parallel-agents | 分发并行代理 |
| subagent-driven-development | 子代理驱动开发 |
| using-git-worktrees | 使用 Git worktrees |
| using-superpowers | 使用 superpowers 简介 |
| verification-before-completion | 完成前验证 |

## 安装使用

将需要的 skill 目录复制到对应平台的 skills 目录：

- **Claude Code**: `~/.claude/skills/`
- **Copilot CLI**: `~/.agents/skills/`
- **Gemini CLI**: 参考 GEMINI.md 配置

## 与原项目的差异

仅一处路径引用修改：
- `brainstorming/SKILL.md` 中的 `skills/brainstorming/visual-companion.md` → `visual-companion.md`

其他所有内容与原项目完全一致。

## License

MIT License