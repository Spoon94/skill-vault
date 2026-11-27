# hao

`hao` 是在 herdr 上做**分档多 agent 协作**的 CLI——herdr 只是通道。它提供三件事：27 个带档位（top/mid/low）的角色目录、按档位派活（简报长度与默认输出上限随档位收紧，贵模型只在最难处花钱）、任务级等待（等的是“这个任务完成”，不是“对方空闲”）。名字与角色的持久化、重启后的恢复是附带能力。角色定义见 `references/roles.md`，完整协作流程见 `references/workflow.md`。

## 前置条件

- POSIX（macOS/Linux；台账依赖 `fcntl`，Windows 原生不适用）
- herdr ≥ 0.9.5，且在 `HERDR_ENV=1` 的 pane 内运行
- python3 ≥ 3.9（仅标准库，无第三方依赖）
- 适用任何 herdr 支持的 CLI agent（`herdr agent start --help` 列出种类）
- `hao` 始终位于 skill 内，不复制、链接或安装到其他位置；用 `python3 <skill目录>/scripts/hao` 调用。下文 `hao` 均是该命令的简写。

## 30 秒上手：按角色派活

```bash
hao doctor                              # 自检
hao name w2:p9 hawk --role reviewer     # → agent hawk + label hao-hawk-reviewer；role=reviewer, tier=mid
hao ask w2:p9 "用三句话说明怎样做好代码评审" --wait --timeout 120   # JSON 带回 status/summary/role/tier/max_lines
```

长任务用异步 + 唤醒；收到 `[HAO_WAKE] ...` 通知后，按通知里的 `hao wait` 命令取结果：

```bash
hao ask w2:p9 "跑完整测试并汇报" --wake "$HERDR_PANE_ID"
hao wait w2:p9 --token <shortid> --timeout 600
```

重启后从 label 恢复名字与角色：

```bash
hao restore --dry-run
hao restore
```

最小的三档配合（细节见 `references/workflow.md`；每个任务都自带上限和超时）：

```bash
hao name w2:p9 atlas --role architect
hao ask w2:p9 "为登录限流写方案与验收标准" --wait --timeout 300
hao name w2:p10 moss --role project-manager
hao ask w2:p10 "把方案拆成任务清单：<上一步 summary>" --wait --timeout 300
hao name w2:p11 fern --role developer
hao ask w2:p11 "实现任务 1" --wait --timeout 300
hao name w2:p12 lens --role reviewer
hao ask w2:p12 "审查任务 1 的改动，只列阻塞问题" --wait --timeout 300
hao name w2:p13 moth --role arbiter
hao ask w2:p13 "只回答通过/不通过；材料：<初审结论>" --wait --timeout 300
```

## 命令面

| 命令 | 作用（`hao <cmd> --help` 有完整说明） |
|---|---|
| `hao name <target> <name> [--role ROLE] [--force] [--dry-run] [--machine MACHINE] [--json]` | 改 agent 名并把 label 设为 `hao-<name>[-role]`；省略 `--role` 沿用现有角色，`--role ""` 清除角色 |
| `hao clear <target> [--force] [--dry-run] [--machine MACHINE] [--json]` | 清除 hao- label 与 agent name |
| `hao suggest <task> [--json] [--live-names NAME] [--live-labels LABEL] [--custom NAME] [--machine MACHINE]` | 按任务关键词选名；`--custom` 校验自定义名 |
| `hao restore [WORKSPACE] [--workspace WORKSPACE] [--all] [--adopt] [--no-adopt] [--dry-run] [--pick PANE] [--machine MACHINE] [--json]` | 从 label 恢复名字与角色 |
| `hao ask <target> <text> [--wait] [--mode MODE] [--wake TARGET] [--timeout SECONDS] [--machine MACHINE] [--strict-ledger] [--text-only] [--max-lines N] [--json]` | 派任务；`--mode` 为 sentinel/lifecycle/file；`--wake` 完成后唤醒；`--text-only` 不给对方 `hao done` 命令 |
| `hao wait <target> [TOKEN] [--token TOKEN] [--timeout SECONDS] [--mode MODE] [--machine MACHINE] [--no-agent] [--accept-unknown] [--json]` | 等任务完成；`--json` 恒输出 JSON |
| `hao done [TOKEN] [--token TOKEN] [--summary TEXT] [--final] [--json]` | 写台账 done 并打印哨兵；JSON 走 stderr |
| `hao cancel <shortid> [--json]` | 只取消等待，不停止对方 |
| `hao abort <shortid> [--interrupt] [--json]` | 作废任务；`--interrupt` 另停对方 |
| `hao stop <target> [--dry-run] [--machine MACHINE] [--json]` | 只停当前这一轮，不读写任务记录 |
| `hao list [WORKSPACE] [--workspace WORKSPACE] [--machine MACHINE] [--json]` | 列出 hao- pane（含 role、tier） |
| `hao status [TARGET] [--text] [--json]` | pane/agent/任务概览（role、tier、group），默认当前 pane |
| `hao say TEXT... [--strict] [--json]` | 发普通 prompt，不建任务 |
| `hao result <shortid> [--target PANE] [--file PATH] [--allow-any-path] [--json]` | 读取结果或显式允许的文件 |
| `hao doctor [--machine MACHINE] [--json]` | 环境/机器自检 |
| `hao clean [--all] [--ttl SECONDS] [--dry-run] [--json]` | 清理终态/孤儿台账与结果目录 |

短别名：`n` name · `c` clear · `r` restore · `a` ask · `w` wait · `d` done · `l` list · `s` suggest · `st` status · `sy` say · `rs` result。所有命令支持 `--json`；`ask`/`wait` 恒 JSON，该 flag 为 no-op。

## 角色目录

27 个角色分五组；角色说明“做什么”，档位决定“怎么派活”。完整职责见 `references/roles.md`。

| 组 | 档位 | 角色 |
|---|---|---|
| 决策 | top | strategist · product-manager · planner · architect · arbiter |
| 协调 | mid | project-manager · orchestrator · synthesizer |
| 设计评审 | mid | designer · ux-designer · reviewer · evaluator · analyst · auditor |
| 实施 | low | developer · frontend-developer · backend-developer · debugger · refactorer · test-engineer |
| 支撑 | low | explorer · researcher · doc-writer · devops-engineer · data-engineer · prompt-engineer · memory-curator |

角色名 7–20 个字符（小写字母和连字符）。命名与角色解耦：`suggest` 只选名字；新增角色只需在 `references/roles.md` 对应表加一行。

## 按档位派活

| 档位 | 简报 | 默认输出上限 |
|---|---|---|
| `top` | 精简简报 | 15 行 |
| `mid` | 与 `low` 共用的完整简报 | 40 行 |
| `low` / 无角色 | 完整简报 | 不限 |

`ask --max-lines N` 覆盖默认值：`0` 不限，负数 exit 2。返回 JSON 的 `role`、`tier`、`max_lines` 反映实际生效值。

## 等待与结果

完成必须有任务级证据：台账 `status=done`，或对方屏幕上的哨兵 `HAO_DONE <token>`；生命周期状态只作活动门槛，不是完成信号。答复载荷按优先级取：`summary`（对方调了 `hao done --summary`）→ 结果文件（file 模式读进 `tail`，文件随即删除）→ `tail`（从屏幕提取）。

`wait` 常用字段：`status`、`summary`、`tail`、`last_line`、`tail_note`、`matched_line`、`result_path`、`result_consumed`。`ask --wait` 的返回还带 `role`、`tier`、`max_lines`，能取到布局时另带 `target_cols`。`tail` 可能包含对方界面的思考过程，`last_line` 是最后一条非 UI 行；屏幕被审批框遮挡时 `tail` 可能为 null 并带 `tail_note`。

任务台账是运行时缓存：默认位于系统临时目录的 `hao-<uid>/tasks`（Linux 有 `XDG_RUNTIME_DIR` 则用其下 `hao/tasks`），`HAO_STATE_DIR` 可覆盖；任务被 `wait`/`result` 取走即删，不使用用户主目录或 XDG 状态目录。

| 模式 | 适用场景 |
|---|---|
| `sentinel`（默认） | 文本哨兵 + 台账；~30 秒快路径后切 agent wait 兜底与大窗口重扫 |
| `lifecycle` | 以对方 `submit_seq` 为活动门槛；派发前若对方仍在 working，最多等 10 秒收尾；必须配 `--wait` |
| `file` | 对方把结果写进 `result.md`；wait 读进 `tail`，删除文件、记录、锁与结果目录（取走即删），`result_consumed` 标记已消费 |

`--timeout` 默认 1800 秒；超时 exit 4，错误信息带 `agent_status` 与下一步提示。

## 派活前要知道的几件事

- **任务文本要自包含、有边界，并带上 `--timeout`。** 对端只能看到你发出的这段文字和它自己的工作目录。实测把一句“审查 PR 7”发给工作目录是 `/tmp` 的 pi，它花了几分钟去找是哪个仓库、哪个 PR，最后真的审了一个已合并的 PR，还在仓库里建了 worktree。
- 对方输入框必须为空；未提交的文字会被一起提交或丢失。
- 给 `low` 档角色设短的 `--timeout`；对方干完活却不发完成信号时，wait 只在超时返回。
- 弱模型不一定调用 `hao done`，`summary` 可能为空；这时看 `tail` / `last_line`。
- 需要审批、或访问不到 hao 的对方用 `ask --text-only`，结果只走文本通道。
- `ask --wait` 返回时对方可能还在 working 一两秒；紧接着派下一个默认模式任务通常没问题。
- 对方 pane 窄于 40 列时 `ask` 会警告：文本哨兵可能因折行认不出，台账通道不受影响；能取到布局时返回里带 `target_cols`。
- `agent_status=unknown` 加 `--accept-unknown`；无 agent 的 shell pane 用 `--no-agent` 或 `--mode file`。
- 跨机器加 `--machine`：未知 machine exit 7，herdr 不可达 exit 8。这条路径只用桩验证过，没有做过端到端的真机验证。
- 不要省略 `--timeout` 做长时间轮询。

## 命名与恢复

名字匹配 `^[a-z]{4,6}$`，per-machine 唯一；label 形如 `hao-<name>-<role>`，是名字与角色的唯一持久载体（零注册表）。旧 label 的非角色段原样保留（tier 为 null）。`restore` 从 label 恢复名字与角色，支持 `--workspace` / `--all` / `--pick` / `--dry-run` / `--adopt`，算法见 `references/restore.md`。

## 控制命令

- `cancel` / `abort`（不带 `--interrupt`）：只作废等待，不停止对方；目标 working 时输出 `peer_running:true`、`next`。
- `abort --interrupt`：先作废任务再停对方；blocked 需要 TTY 或 0600 授权。
- `stop <target>`：只停当前这一轮，不依赖任务记录；blocked 同样需要授权。
- 过期的 running 记录在 `clean`/`doctor` 中先查 target：目标已不存在才删，仍 working/blocked/unknown 或状态不可读则保留。
- 取消记录何时回收、审批文件格式等细节见 `references/protocol.md`。

## 输出契约与退出码

结果走 stdout（JSON 或单行文本）；失败原因走 stderr 一行；先看退出码再读 stderr。

```text
hao name: name 'forge' already taken by agent on w2:p9 (exit 6)
```

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 2 | 用法/参数错误 |
| 3 | target/task/result 不存在 |
| 4 | 超时 |
| 5 | blocked 或缺少授权 |
| 6 | 冲突、歧义、name taken |
| 7 | machine/profile 不可用 |
| 8 | herdr/server 错误 |
| 9 | 协议错误 |
| 10 | cancelled |

完整错误码与 JSON schema 见 `references/protocol.md`。

## 目录

```
hao/
├── SKILL.md                    # skill 入口与约束
├── README.md                   # 本文件
├── scripts/
│   ├── hao                     # CLI 主文件
│   ├── waiting.py              # 等待内核；加载时 exec 合并进 hao 命名空间，不是独立模块
│   ├── ledger.py               # 任务台账（per-shortid 锁 + 字段 merge）
│   └── names.py                # 词表与角色目录解析
└── references/
    ├── names.md                # 40 组 × 40 个名字及中英关键词
    ├── roles.md                # 27 个角色与档位
    ├── protocol.md             # 等待协议、错误码、JSON schema
    ├── restore.md              # label 解析、pre-flight、adopt、清理
    └── workflow.md             # 五步协作流程与失败处理
```

## 测试

```bash
cd tests/hao
python3 -m unittest discover -s . -p 'test_*.py'       # 单元（497 个）
python3 integration/test_integration.py                  # 集成冒烟（需 HERDR_ENV=1）
python3 live/run_live.py --list                          # 可选真机场景（需 HERDR_ENV=1 + HERDR_WORKSPACE_ID；--quick 约 5 分钟，完整约 8 分钟）
```

## 从旧版本升级

旧版本（PR #9 之前）的台账在 `~/.local/state/hao/tasks/`；升级时若有未取走的任务，用 `HAO_STATE_DIR=~/.local/state/hao/tasks python3 <skill目录>/scripts/hao wait <target> --token <token>` 读取。只读旧目录，不迁移、不覆盖新台账。

## 设计文档与来源

- 当前设计：[docs/superpowers/specs/2026-11-26-hao-skill-design.md](../docs/superpowers/specs/2026-11-26-hao-skill-design.md)
- 历史设计：[docs/superpowers/specs/2026-11-22-herdr-agent-ops-design.md](../docs/superpowers/specs/2026-11-22-herdr-agent-ops-design.md)

全新创建（非 vendored）；名字词表由脚本生成并经保留字 + 敏感词校验。MIT。
