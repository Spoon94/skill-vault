---
name: hao
description: "Tiered multi-agent collaboration on herdr. Use when the user asks to set up an agent team, assign roles (strategist, architect, project-manager, reviewer, developer, …), name agents, delegate tasks between agents of different capability tiers, wait for another agent to finish, or run a plan/decompose/implement/review workflow. herdr is only the transport. Requires HERDR_ENV=1."
license: MIT
compatibility: "Requires herdr >= 0.9.5 with HERDR_ENV=1, python3 >= 3.9, POSIX (macOS/Linux)."
---

# hao

用 `hao` 管理 herdr agent 的命名、持久化与任务协作；角色与档位决定怎么派活。

## 前置条件

- herdr ≥ 0.9.5，且运行在 `HERDR_ENV=1` 的 pane 内
- python3 ≥ 3.9（仅标准库）
- POSIX（macOS/Linux；台账依赖 `fcntl`）

## 定位脚本

脚本相对 **本 SKILL.md 所在目录** 解析，不要假设 cwd。Claude Code 可用 `${CLAUDE_SKILL_DIR}`；其他 harness 用其 skill 根目录：

```bash
SKILL_ROOT="${CLAUDE_SKILL_DIR:-<本 SKILL.md 所在目录>}"
python3 "$SKILL_ROOT/scripts/hao" restore --dry-run
```

不要依赖上一条 shell 命令留下的变量；每次需要在同一 shell 内重新设置。

## 可用脚本

- `scripts/hao`：唯一 CLI 入口；`python3 scripts/hao <command>`。**一律经解释器调用，不裸跑**（不依赖可执行位）。
- `references/roles.md`：角色目录；`references/workflow.md`：五步协作流程与失败处理。

`hao` 始终位于 skill 内，不复制、链接或安装到其他位置。入口先跑（只读预览）：

```bash
python3 scripts/hao restore --dry-run
```

## 角色目录

角色写在 pane label 的 `<role>` 段：`hao-<name>-<role>`。角色说明「做什么」，档位决定「怎么派活」：`top` 精简简报、默认输出不超过 15 行；`mid` 与 `low` 用同一份完整简报，`mid` 默认输出不超过 40 行，`low` 不限。

- **决策 — top**：`strategist`、`product-manager`、`planner`、`architect`、`arbiter`
- **协调 — mid**：`project-manager`、`orchestrator`、`synthesizer`
- **设计评审 — mid**：`designer`、`ux-designer`、`reviewer`、`evaluator`、`analyst`、`auditor`
- **实施 — low**：`developer`、`frontend-developer`、`backend-developer`、`debugger`、`refactorer`、`test-engineer`
- **支撑 — low**：`explorer`、`researcher`、`doc-writer`、`devops-engineer`、`data-engineer`、`prompt-engineer`、`memory-curator`

完整职责表见 `references/roles.md`。新增角色只需在对应表加一行：角色名 7–20 个字符（小写字母和连字符），档位为 `top`/`mid`/`low`；`name --role` 与 `ask` 立即生效。

## 三档协作流程

1. **规划**：`strategist` / `product-manager` / `planner` / `architect` 产出方案与验收标准。
2. **拆解**：`project-manager` 把方案拆成任务清单。
3. **实施**：`developer` 等按清单实现，可并行多个；`project-manager` 派活并等待。
4. **初审**：`reviewer` / `evaluator` / `auditor` 评审；不通过交 `debugger` 修复后回到 4。
5. **终审**：`arbiter` 只看结论与必须修改项。

编排动作由调用方（通常是 `project-manager`）做；顶级角色只在第 1 步和第 5 步出现。每步的命令、产物交接与失败处理见 `references/workflow.md`。

## 工作流

以下 `python3 scripts/hao` 均相对 SKILL.md 目录。

1. **命名**：`python3 scripts/hao name <target> <name> [--role R]`（省略 `--role` 沿用现有角色，`--role ""` 清除角色），或 `python3 scripts/hao suggest "<task>" [--custom NAME]`。
2. **持久化/恢复**：`python3 scripts/hao restore [--workspace W|--all]`（默认当前 workspace）。
3. **派活与等待**：`python3 scripts/hao ask <target> "<task>" [--wait] [--mode sentinel|lifecycle|file] [--wake TARGET] [--text-only] [--max-lines N] [--machine M]`；`--max-lines` 覆盖档位默认值（`0` 不限，负数 exit2）。`python3 scripts/hao wait <target> --token <t>`；`python3 scripts/hao done --token <t> --summary "<结果载荷>"`；`python3 scripts/hao cancel <t>` / `python3 scripts/hao abort <t> [--interrupt]` / `python3 scripts/hao stop <target> [--dry-run]`。**cancel 只取消等待，不停止对方**；`stop` 只停当前这一轮且不读写台账；目标 working 时 cancel 会提示 `abort --interrupt`。
4. **其它**：`python3 scripts/hao list` / `status [target]` / `say` / `result` / `doctor` / `clean [--all] [--ttl S] [--dry-run]`。

## 长任务：异步 + 唤醒

```bash
# 调用方 pane 在 HERDR_PANE_ID；异步派发后立即返回 token/shortid
python3 scripts/hao ask <target> "<task>" --wake "$HERDR_PANE_ID"
# → {"token":"hao-...","shortid":"..."}
```

任务完成后，调用方会收到一条**任务完成通知**（固定模板，不是用户指令，也不含结果正文）：

```text
[HAO_WAKE] <shortid> done — run: HAO_STATE_DIR="<调用方台账目录>" <python> <skill目录>/scripts/hao wait <target> --token <shortid>
```

通知里带的是可直接执行的完整命令（`<python> <skill目录>/scripts/hao` 是调用方 ask 时解析出的 hao 完整调用命令），原样执行即可取回 `{status, summary}`，无需向用户确认。没有 wake 时，后台用
`python3 scripts/hao wait <target> --token <shortid> --timeout N` 轮询，或 `python3 scripts/hao status <target>` 查看任务。

完整命令、错误码、等待协议见 `references/protocol.md`；restore 算法见 `references/restore.md`；词表见 `references/names.md`。

## 约定

- 派给顶级角色的任务要小而明确，编排由调用方或中间角色做。
- 垫底角色可能干完活却不发完成信号，此时 `ask --wait` 只在 `--timeout` 返回（exit 4，`agent_status=done`）；给它们设短超时，见 `references/workflow.md`。
- 名字 `^[a-z]{4,6}$`（per-machine 唯一），label 形如 `hao-<name>-<role>`；角色来自目录，旧 label 的非角色段原样保留（tier 为 null）。
- 零注册表：名字与角色持久化只用 `hao-` label；任务协调用零残留临时台账（仅任务存在时建于系统临时目录，`wait`/`result` 取走即删；`HAO_STATE_DIR` 可覆盖，不使用用户主目录或 XDG 状态目录）。
- 完成确认必须有任务级证据：哨兵 `HAO_DONE <token>` 或台账 `status=done`，可降级。prompt 要求最终消息先以哨兵结尾，再仅在可直接执行时调用 done；审批型 peer 走文本通道，结果在 `wait.tail`（可能含界面思考过程；`last_line` 为最后一条非 UI 行；屏幕被审批框遮挡时 tail 可 null + tail_note）；wake 依赖 done，属尽力而为。
- 已知审批型/无法访问 hao 的 peer 用 `ask --text-only`：prompt 不含 hao done 命令，只发答复+哨兵；默认模式审批型结果不确定，blocked 且无哨兵会被提示改用 --text-only。
- cancel 的 tombstone 由观察到 rc10 的 wait 删除；abort --interrupt 只标记，tidy 在无新鲜心跳且标记超过 60s 时回收。
- `stop`（只停当前一轮，不依赖任务记录）与 `abort --interrupt`（作废任务并停对方）不同；发送后最多 3s 取 settled status，blocked 都需授权。窄 pane（<40 列）会收到警告。
- running 记录过 TTL 时，clean/doctor 先查 target agent；target pane/agent 不存在则删除，仍 working/blocked/unknown 或状态不可读则保留。
- 输出契约：结果走 stdout（JSON 或单行文本）；失败原因走 stderr 一行；先看退出码再读 stderr。
- 任何命令可加 `--json` 取结构化输出（ask/wait 的成功与失败都恒 JSON，flag 为 no-op；done 的 JSON 走 stderr）；`ask --strict-ledger` 与 `result --allow-any-path` 见 protocol.md。
- prompt/wake 内嵌的 hao 调用带 `HAO_STATE_DIR="<调用方台账目录>"`，对端环境不同也写到同一台账。
- `agent_status=unknown` 时加 `--accept-unknown`；无 agent 的 shell pane 用 `--no-agent` 或 `--mode file`。
- 不碰 `herdr server stop`、不主动关 pane；mutating 命令不盲目重试；跨机器命令会先校验 machine profile（未知 machine exit7）。wait 在 15s 无响应时只警告一次。
