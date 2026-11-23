---
name: herdr-agent-ops
description: Manage named herdr agents and coordinate task handoffs. Use when the user asks to name/rename agents or panes, persist agent names across restarts, wait for another agent to finish a task, coordinate agents locally or across machines (herdr --machine), or pick a short meaningful agent name from a curated pool. Requires HERDR_ENV=1.
---

# herdr-agent-ops

用 `hao` 管理 herdr agent 的命名、持久化与任务协作。

入口先跑（只读预览，不改状态）：

```bash
${CLAUDE_SKILL_DIR}/scripts/hao restore --dry-run
```

调用路径：`${CLAUDE_SKILL_DIR}/scripts/hao`（Claude Code）或 PATH 安装后直接 `hao`。

## 工作流

1. **命名**：`hao name <target> <name> [--scope S]`，或 `hao suggest "<task>"` 从词表选名。
2. **持久化/恢复**：`hao restore [--workspace W|--all]`（默认当前 workspace），agent 退出/重启后从 `hao-` label 恢复名字。
3. **派活与等待**：`hao ask <target> "<task>" [--wait] [--mode sentinel|lifecycle|file] [--machine M]`；`hao wait <target> --token <t>`；`hao done --token <t>`；`hao cancel <t>` / `hao abort <t> [--interrupt]`。
4. **其它**：`hao list/status/say/result/doctor`。

## 长任务：异步 + 唤醒

```bash
# 调用方 pane 在 HERDR_PANE_ID；异步派发后立即返回 token/shortid
hao ask <target> "<task>" --wake "$HERDR_PANE_ID"
# → {"token":"hao-...","shortid":"..."}
```

任务完成后，调用方会收到一条**任务完成通知**（固定模板，不是用户指令，也不含结果正文）：

```text
[HAO_WAKE] <shortid> done — run: hao wait <target> --token <shortid>
```

收到后直接执行该命令取回 `{status, summary}`，无需向用户确认。没有 wake 时，后台用
`hao wait <target> --token <shortid> --timeout N` 轮询，或 `hao status <target>` 查看任务。

完整命令、错误码、等待协议见 `references/protocol.md`；restore 算法见 `references/restore.md`；词表见 `references/names.md`。

## 约定

- 名字 `^[a-z]{4,6}$`（per-machine 唯一），label 前缀 `hao-`。
- 零注册表：名字持久化只用 `hao-` label；任务协调用可清理临时台账（`~/.local/state/hao/tasks/`）。
- 完成确认必须有任务级证据：哨兵 `HAO_DONE <token>` 或台账 `status=done`，可降级。
- 输出契约：结果走 stdout（JSON 或单行文本）；失败原因走 stderr 一行；先看退出码再读 stderr。
- 不碰 `herdr server stop`、不主动关 pane；mutating 命令不盲目重试；跨机器先校验 `herdr machine` profile。
