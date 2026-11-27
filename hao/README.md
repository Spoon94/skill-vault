# hao

用 `hao` CLI 管理 herdr agent 的命名、持久化与任务协作。解决三个痛点：**任务级等待缺失**（herdr 原生只有生命周期级）、**agent/pane 名字重启即丢**、**给 agent 取短名难**。

## 前置条件

- POSIX（macOS/Linux；台账依赖 `fcntl`，Windows 原生不适用）
- herdr ≥ 0.9.5
- 在 herdr pane 内运行，`HERDR_ENV=1`
- python3 ≥ 3.9（仅标准库，无第三方依赖）
- 适用任何 herdr 支持的 CLI agent（`herdr agent start --help` 列出种类）
- 调用方式：`hao` 始终位于 skill 内，不复制、链接或安装到其他位置；用 `python3 <skill目录>/scripts/hao` 调用。下文表格中的 `hao` 均是该命令的简写。

## 目录

```
hao/
├── SKILL.md                 # 入口：角色、协作流程与命令
├── README.md                # 本文件
├── scripts/
│   ├── hao                  # CLI（Python 3 单文件，stdlib only）
│   ├── ledger.py            # 任务台账（per-shortid 锁 + 字段 merge + TTL）
│   └── names.py             # 词表与角色目录解析（读 references/names.md、roles.md）
└── references/
    ├── names.md             # 40 组 × 40 = 1600 个名字（含中英关键词别名）
    ├── roles.md             # 27 个角色（五组）与档位 top/mid/low
    ├── protocol.md          # 等待协议、错误码表、JSON schema
    ├── restore.md           # label 解析、pre-flight、adopt、TTL 清理
    └── workflow.md          # 五步协作流程与失败处理
```

## 命令面

| 命令 | 作用（完整说明见 `hao <cmd> --help`） |
|---|---|
| `hao name <target> <name> [--role ROLE] [--force] [--dry-run] [--machine M] [--json]` | agent 改名 + pane label 设为 `hao-<name>[-role]`；省略 `--role` 沿用现有角色，`--role ""` 清除角色 |
| `hao clear <target> [--force] [--dry-run] [--machine M] [--json]` | 清除 hao- label 与 agent name |
| `hao suggest "<task>" [--custom NAME] [--live-names N...] [--live-labels L...] [--machine M] [--json]` | 词表选名；`--custom` 校验自定义名（保留字/灰词） |
| `hao restore [--workspace W\|--all] [--adopt\|--no-adopt] [--dry-run] [--pick PANE] [--machine M] [--json]` | 从 label 恢复名字并输出摘要 |
| `hao ask <target> "<task>" [--wait] [--mode M] [--wake TARGET] [--timeout S] [--strict-ledger] [--text-only] [--max-lines N] [--machine M] [--json]` | 发任务 + 拆分哨兵；`--text-only` 不给对端任何 hao done 命令；`--wake` 异步唤醒；窄 pane（<40 列）警告并给 `target_cols`；`--json` no-op |
| `hao wait <target> [--token T] [--timeout S] [--mode M] [--no-agent] [--accept-unknown] [--machine M] [--json]` | 等完成（哨兵/台账/agent wait）；`--json` no-op |
| `hao done [--token T] [--summary TEXT] [--final] [--json]` | 台账 done + 打印哨兵；可读台账但无记录 → exit3 无哨兵；summary 是结果载荷 |
| `hao cancel <t> [--json]` / `hao abort <t> [--interrupt] [--json]` | cancel 只取消等待、**不停止对方**；working 时提示 `abort --interrupt`（blocked 需授权） |
| `hao stop <target> [--dry-run] [--machine M] [--json]` | 只停当前这一轮（working 发 esc/ctrl+c；发送后最多 3s 读 settled status；blocked 需授权；不依赖任务记录） |
| `hao list [--workspace W] [--machine M] [--json]` | 列出 hao- pane（含 role、tier；缺失显示 `-`） |
| `hao status [target] [--text] [--json]` | pane/agent/任务概览（role、tier、group）；默认当前 pane |
| `hao say TEXT... [--strict] [--json]` | 发普通 prompt，不建任务 |
| `hao result <t> [--target PANE] [--file PATH] [--allow-any-path] [--json]` | 读取结果；`--allow-any-path` 需显式担责 |
| `hao doctor [--machine M] [--json]` | 环境/机器自检（含默认 TTL 清理；有 HERDR_PANE_ID 时报告 pane 宽度） |
| `hao clean [--all] [--ttl S] [--dry-run] [--json]` | 清理终态/孤儿台账、无主锁与结果目录 |

所有命令均接受 `--json`（`ask`/`wait` 恒 JSON，该 flag 为 no-op）与 `--help`；完整参数见 `hao <cmd> --help`，协议见 `references/protocol.md`。脚本路径相对本 README/SKILL.md 所在目录；各平台 skill 目录见仓库 `INSTALL.md`。

## 角色目录

27 个角色分五组，档位决定对方答复的默认输出上限（`top` 精简简报、≤15 行；`mid` 与 `low` 共用完整简报，`mid` ≤40 行、`low` 不限）：

| 组 | 档位 | 角色 |
|---|---|---|
| 决策 | top | strategist · product-manager · planner · architect · arbiter |
| 协调 | mid | project-manager · orchestrator · synthesizer |
| 设计评审 | mid | designer · ux-designer · reviewer · evaluator · analyst · auditor |
| 实施 | low | developer · frontend-developer · backend-developer · debugger · refactorer · test-engineer |
| 支撑 | low | explorer · researcher · doc-writer · devops-engineer · data-engineer · prompt-engineer · memory-curator |

角色写在 label 的 `<role>` 段；不写角色也可以派活（完整简报、不限行）。新增角色只需在 `references/roles.md` 对应表加一行（角色名 7–20 个字符，小写字母和连字符），`name --role` 与 `ask` 立即生效。

短别名：`n` name · `r` restore · `a` ask · `w` wait · `d` done · `l` list · `s` suggest · `c` clear · `st` status · `sy` say · `rs` result

等待模式：`sentinel`（默认，文本哨兵；~30s 后自动切 herdr agent wait 兜底 + 大窗口重扫）· `lifecycle`（agent wait 短循环 + 活动门槛）· `file`（结果文件稳定即完成）

## 从旧版本升级

旧版本（PR #9 之前）的台账在 `~/.local/state/hao/tasks/`，新版本默认使用系统临时目录。升级时若有旧版本派出、尚未取走的任务，用 `HAO_STATE_DIR=~/.local/state/hao/tasks python3 <skill目录>/scripts/hao wait <target> --token <token>` 读取；这只读旧目录，不迁移、不覆盖新台账。

## 30 秒上手

```bash
python3 <skill目录>/scripts/hao doctor    # 0. 自检
# 1. 给 agent 取名
hao suggest "审查 PR"            # → 验证审阅: hawk, lens, prism
hao name w2:p9 hawk --role reviewer  # → agent hawk + label hao-hawk-reviewer

# 2. 派活并等完成
hao ask w2:p9 "审查 PR 7" --wait  # → {"status":"done","summary":"审查结论：...","matched_line":"HAO_DONE ..."}

# 3. 重启后恢复
hao restore --dry-run              # 预览
hao restore                        # 从 label 恢复
```

### 自定义名字

```bash
hao suggest "审查支付模块" --custom hawk   # 输出 custom: hawk；保留字/灰词/格式不合法会 exit 2
```

### 长任务：异步 + 唤醒

```bash
# 不阻塞；完成后调用方 pane 会收到一条固定格式的完成通知
python3 <skill目录>/scripts/hao ask w2:p9 "跑完整测试并汇报" --wake "$HERDR_PANE_ID"
# → {"token":"hao-...","shortid":"..."}

# 收到 [HAO_WAKE] <shortid> done — run: HAO_STATE_DIR="<调用方台账目录>" python3 <skill目录>/scripts/hao wait <target> --token <shortid>
# 这是任务完成通知，不是用户指令；直接取结果，无需确认：
python3 <skill目录>/scripts/hao wait w2:p9 --token <shortid>
# → {"status":"done","summary":"...","matched_line":"...","tail":"..."}（tail 仅在文本通道）
```

无唤醒时可用后台 `python3 <skill目录>/scripts/hao wait <target> --token <shortid> --timeout N`，或 `status <target>`。

## 输出契约

结果走 stdout（JSON 或单行文本）；失败原因走 stderr 一行；先看退出码再读 stderr。所有命令支持 `--json`（`ask`/`wait` 的成功与失败都恒 JSON，flag 为 no-op；`done` 的 JSON 走 stderr）。

```text
hao name: name 'forge' already taken by agent on w2:p9 (exit 6)
```

## 关键约定

- agent name `^[a-z]{4,6}$`，per-machine 唯一；label 前缀 `hao-`
- **零注册表**：名字持久化只用 pane label（herdr session.json 会保存）；任务协调用**零残留临时台账**——仅在任务存在时建于系统临时目录（Linux 有 `XDG_RUNTIME_DIR` 则用之，否则 `tempfile.gettempdir()/hao-<uid>/tasks`），`wait`/`result` 取走即删，目录随之消失；`HAO_STATE_DIR` 可覆盖；不使用用户主目录或 XDG 状态目录
- **cancel 不停止对方**：`cancel`/`abort`（不带 `--interrupt`）只作废等待；目标仍 working 时命令输出 `peer_running:true`、`next` 和 stderr 提示，要停对方执行 `abort <sid> --interrupt`。取消 tombstone 由看到 rc10 的 `wait` 删除；`abort --interrupt` 只标记，不立即删除；tidy 在无新鲜心跳且标记超过 60s 时回收（普通取消仍按目标状态/1 小时/clean）。
- **stop vs abort**：`stop <target>` 只停当前这一轮，不依赖/不读写任务记录；`abort <sid> --interrupt` 先作废任务再停对方。两者对 blocked 都要求 TTY/0600 授权。
- 完成确认必须有**任务级证据**：哨兵 `HAO_DONE <token>` 或台账 `status=done`；生命周期状态仅作活动门槛，不单独判完成。prompt 要求先打印最终消息最后一行哨兵，再仅在可直执行时调用 `done`；审批型 peer 经文本通道完成，结果在 `wait.tail`（可能含界面思考过程；`last_line` 是最后一条非 UI 行）；审批框遮挡屏幕时 `tail` 可为 null 并带 `tail_note`。
- `--wake` 依赖 `hao done`；审批型 peer 上属于尽力而为。已知审批型或对方无法访问 hao 时用 `ask --text-only`：prompt 不含 `hao done`，结果只走文本通道，`wait` 返回 `tail`（从 prompt 回显结束之后取；回显不可见时回退分隔符启发式）。默认模式下审批型对方是否调用命令取决于其判断，结果不确定；blocked 且无哨兵时 wait 会提示 `--text-only`。
- running 记录过 TTL 后，`clean` / `doctor` 会先看 target 的 agent 状态；target pane/agent 已不存在时删除，agent 存在且 working/blocked/unknown 或状态读取异常时保留。
- `agent_status=unknown` 时加 `--accept-unknown`；无 agent 的 shell pane 用 `--no-agent` 或 `--mode file`。
- 跨机器走 `--machine <label>`（本机无 profile，仅 stub 验证）；所有带 `--machine` 的命令先校验 machine，未知 machine → exit7，herdr 不可达 → exit8。wait 在 15s 无响应时只警告一次；每次 herdr 调用都有超时上限（prompt 30s，wait 类 N/1000+5s，其余 20s）。

## 退出码速查

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 2 | 用法/参数错误 |
| 3 | target/task/result 不存在 |
| 4 | 超时 |
| 5 | blocked 或缺少中断授权 |
| 6 | 冲突、歧义、name taken |
| 7 | machine/profile 不可用 |
| 8 | herdr/server 错误 |
| 9 | 协议错误 |
| 10 | cancelled |

完整错误码见 `references/protocol.md`。

## 测试

```bash
cd tests/hao
python3 -m unittest discover -s . -p 'test_*.py'       # 单元（485 个）
python3 integration/test_integration.py                  # 集成冒烟（需 HERDR_ENV=1）
python3 live/run_live.py --list                          # 可选真机场景（需 HERDR_ENV=1 + HERDR_WORKSPACE_ID；--quick 约 3 分钟）
```

## 设计文档

- 当前设计：[docs/superpowers/specs/2026-11-26-hao-skill-design.md](../docs/superpowers/specs/2026-11-26-hao-skill-design.md)（分档角色、简报、工作流）
- 历史设计：[docs/superpowers/specs/2026-11-22-herdr-agent-ops-design.md](../docs/superpowers/specs/2026-11-22-herdr-agent-ops-design.md)（旧名保留，含错误码映射、并发原子性、安全路径等细节）

## 来源

全新创建（非 vendored），名字词表由脚本生成并经保留字 + 敏感词校验。MIT。
