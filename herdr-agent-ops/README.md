# herdr-agent-ops

用 `hao` CLI 管理 herdr agent 的命名、持久化与任务协作。解决三个痛点：**任务级等待缺失**（herdr 原生只有生命周期级）、**agent/pane 名字重启即丢**、**给 agent 取短名难**。

## 目录

```
herdr-agent-ops/
├── SKILL.md                 # 入口：何时用、三条工作流
├── README.md                # 本文件
├── scripts/
│   ├── hao                  # CLI（Python 3 单文件，stdlib only）
│   ├── ledger.py            # 任务台账（per-shortid 锁 + 字段 merge + TTL）
│   └── names.py             # 词表解析（读 references/names.md）
└── references/
    ├── names.md             # 40 组 × 40 = 1600 个名字（含中英关键词别名）
    ├── protocol.md          # 等待协议、错误码表、JSON schema
    └── restore.md           # label 解析、pre-flight、adopt、TTL 清理
```

## 命令面

| 命令 | 作用 |
|---|---|
| `hao name <target> <name> [--scope S]` | agent 改名 + pane label 设为 `hao-<name>[-scope]` |
| `hao suggest "<task>"` | 从词表选名（关键词选组 + per-machine 避重） |
| `hao restore [--workspace W\|--all]` | agent 退出/重启后从 label 恢复名字 |
| `hao ask <target> "<task>" [--wait] [--mode M]` | 发任务 + 拆分哨兵（防回显）；`--wait` 内联等 |
| `hao wait <target> --token <t> [--mode M]` | 等完成（哨兵/台账 done/agent wait 兜底） |
| `hao done --token <t> [--summary] [--final]` | 对端写台账 done + 打印哨兵 |
| `hao cancel <t>` / `hao abort <t> [--interrupt]` | 取消（幂等）/ 中断（blocked 需用户授权） |
| `hao list` / `status` / `say` / `result` / `doctor` | 辅助命令 |

短别名：`n` name · `r` restore · `a` ask · `w` wait · `d` done · `l` list · `s` suggest · `c` clear · `st` status · `sy` say · `rs` result

等待模式：`sentinel`（默认，文本哨兵；~30s 后自动切 herdr agent wait 兜底 + 大窗口重扫）· `lifecycle`（agent wait 短循环 + 活动门槛）· `file`（结果文件稳定即完成）

## 快速开始

```bash
# 1. 给 agent 取名
hao suggest "审查 PR"            # → 验证审阅 [hawk, lens, prism]
hao name w2:p9 hawk --scope api  # → agent hawk + label hao-hawk-api

# 2. 派活并等完成
hao ask w2:p9 "审查 PR 7" --wait  # → 哨兵确认后返回

# 3. 重启后恢复
hao restore --dry-run              # 预览
hao restore                        # 从 label 恢复
```

## 关键约定

- agent name `^[a-z]{4,6}$`，per-machine 唯一；label 前缀 `hao-`
- **零注册表**：名字持久化只用 pane label（herdr session.json 会保存）；任务协调用可清理临时台账（`~/.local/state/hao/tasks/`）
- 完成确认必须有**任务级证据**：哨兵 `HAO_DONE <token>` 或台账 `status=done`；生命周期状态仅作活动门槛，不单独判完成
- 跨机器走 `--machine <label>`（本机无 profile，仅 stub 验证）

## 测试

```bash
cd tests/herdr-agent-ops
python3 -m unittest discover -s . -p 'test_*.py'       # 单元（91 个）
python3 integration/test_integration.py                  # 集成冒烟（需 HERDR_ENV=1）
```

## 设计文档

完整设计稿（33 轮 forge 审核）见 `docs/superpowers/specs/2026-11-22-herdr-agent-ops-design.md`，含错误码映射、并发原子性、安全路径（dirfd 链）等细节。

## 来源

全新创建（非 vendored），名字词表由脚本生成并经保留字 + 敏感词校验。MIT。
