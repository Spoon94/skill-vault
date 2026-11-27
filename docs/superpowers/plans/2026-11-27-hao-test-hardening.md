# hao 测试加固：lifecycle 派发门槛 + 补单元测试缺口 + 真机场景套件

> 分工：quill 设计并验收，verse 实施。分支 `refactor/hao-waiting-module`（PR #12，尚未合并）。
> 用户要求三项都做。分两轮派发：**第一轮 = A + B**，**第二轮 = C**（C 的规格在本文档第三节，第一轮验收后补全）。

## 背景（2026-11-27 实测）

- **单元测试覆盖率 85.1%**（380 个测试，`python3 tests/hao/tools/coverage.py`）；加集成冒烟 85.5%；再加 23 步真机场景 86.6%。
- **真机场景没有固化**：本会话在真实 herdr + 真实 agent 上验证过约 50 个不同场景，仓库里只有集成冒烟那几步。
- **lifecycle 模式连续派活必败**：`ask --mode lifecycle` 在上一个 `wait` 刚返回时派出 → exit 6（复现 3/3）。原因是派发前门槛拒绝 working 的对方，而对方答完后还会 working 1.7–2.5 秒（pi 实测）。默认 sentinel 模式无此问题。

---

## A. lifecycle 模式：对方收尾时有界等待后再派发

**文件**：`hao/scripts/hao`（`cmd_ask`）、`hao/references/protocol.md`、测试。

**现状**（`cmd_ask`，取快照之后）：

```python
    submit_seq, st, snapshot_rc = _agent_snapshot(pane, machine)
    if snapshot_rc:
        return snapshot_rc
    if mode == "lifecycle" and not wait:
        return fail(2, "lifecycle mode requires --wait")
    if mode == "lifecycle" and st in ("working", "blocked", "unknown"):
        return fail(6, f"lifecycle mode needs an idle agent; {pane} is {st}")
```

**改法**：lifecycle 模式下，对方 `working` 时有界等待其 settle，再重新取快照；`blocked` / `unknown` 仍立即 exit 6。

```python
LIFECYCLE_SETTLE_SECONDS = 10      # 模块级常量，放在其它超时常量旁
...
    if mode == "lifecycle" and not wait:
        return fail(2, "lifecycle mode requires --wait")
    if mode == "lifecycle" and st == "working":
        # A peer that has just finished its previous task stays `working`
        # for a moment (measured 1.7-2.5s on pi); wait for it to settle
        # instead of refusing the dispatch.
        deadline = time.time() + LIFECYCLE_SETTLE_SECONDS
        while time.time() < deadline:
            time.sleep(0.5)
            submit_seq, st, snapshot_rc = _agent_snapshot(pane, machine)
            if snapshot_rc or st != "working":
                break
        if snapshot_rc:
            return snapshot_rc
    if mode == "lifecycle" and st in ("working", "blocked", "unknown"):
        return fail(6, f"lifecycle mode needs an idle agent; {pane} is {st}")
```

要点：settle 后必须**重新取快照**（`submit_seq` 要以 settle 后的状态为基线，否则活动门槛会误判）；超时仍是 working 时沿用现有 exit 6 与消息。

**测试**（stub herdr + `HAO_STATE_DIR` 临时目录；`cmd_ask(..., wait=False)`）：
1. `agent get` 前 3 次 working、之后 idle → 派发发生（`agent prompt` 被调用一次），rc 0。
2. 一直 working → exit 6，消息含 "needs an idle agent"；patch `LIFECYCLE_SETTLE_SECONDS` 为小值（或假时钟）避免真等 10 秒。
3. blocked → 立即 exit 6，不进入 settle 轮询（`time.sleep` 未被调用）。
4. unknown → 立即 exit 6。
5. 默认 sentinel 模式 + 对方 working → 立即派发（行为不变，无 settle 等待）。

**文档**：`protocol.md`「模式差异」的 lifecycle 一句补上：派发前若对方仍在收尾（working），最多等 10 秒再派发；blocked / unknown 仍立即 exit 6。

**提交**：`fix(hao): lifecycle mode waits for a working peer to settle before dispatch`

---

## B. 补单元测试缺口

**目标**：`python3 tests/hao/tools/coverage.py` 的整体语句覆盖率 **≥ 92%**，且下表每个函数不低于给定下限。基线 85.1%。

| 函数 | 文件 | 当前 | 下限 | 要覆盖的分支 |
|---|---|---|---|---|
| `cmd_restore` | hao | 60/98 | 90% | 真实恢复成功；pane rename 失败 / agent rename 失败 → partial failures exit 6；shell-only 跳过；`--no-adopt` 已命名跳过；`--all`；`workspace_not_found` → 空；名字冲突 exit 6；无 hao- pane |
| `_wait_unified` | waiting.py | 107/143 | 90% | 门槛：blocked → 5 + 提示、exited/closed → 3、unknown → 9（sentinel）/ 6（lifecycle）、herdr 故障 → 8；放弃前重扫命中哨兵 → done；已验证哨兵在门槛上完成；超时出口；backstop 分支（agent wait 到期继续、重扫命中、确认不通过继续等）；working 分支的 agent wait 非 timeout 错误 → 8；lifecycle 无活动 → 9 |
| `_wait_file` | waiting.py | 47/62 | 88% | 超时 → 4；blocked → 5；exited → 3；台账丢失回退约定路径；文件大小未稳定继续等；`--no-agent` |
| `run_herdr` | hao | 26/38 | 85% | 调用超时 → rc 8（消息含秒数与命令摘要）；启动失败 → "herdr unavailable"；SIGTERM 处理 → SystemExit；处理器恢复 |
| `cmd_abort` / `_abort_approved` | hao | 49/60, 14/19 | 85% / 80% | 无授权 → 5；`HAO_ABORT_ALLOW=1`；0600 授权文件含 shortid；其它 env 值 → 2；记录不存在 → 3 |
| `cmd_stop` | hao | 46/55 | 85% | 已空闲 → `sent: []`；working → 发送按键 + settled 轮询；blocked 无授权 → 5；unknown → 9；无 agent → 3；dry-run |
| `cmd_clear` | hao | 25/35 | 85% | 真实清除；非 hao label 需 `--force` → 6；失败分支 |
| `cmd_result` | hao | 32/40 | 85% | 路径越界 → 2；`--allow-any-path`；`--file`；记录不存在 → 3；读后删除 |
| `safe_read` | hao | 27/33 | 85% | 路径穿越被拒；符号链接逃逸；文件不存在；非普通文件 |
| `cmd_doctor` | hao | 40/52 | 80% | 各检查项的失败分支（python 版本、herdr 缺失、`HERDR_ENV` 未设、状态目录不可写、台账失败、窄 pane） |
| `_machine_preflight` | hao | 10/14 | 75% | 未知 machine → 7；herdr 故障 → 8 |
| `_agent_snapshot` | hao | 8/12 | 75% | agent_not_found；非法 JSON；错误码 |
| `_wait_round_rec` | waiting.py | 4/8 | 100% | heartbeat 抛异常 → 回退只读；都失败 → `{}` |
| `_confirm_sentinel` / `_agent_status_gate` / `_sentinel_scan_tail` | waiting.py | 13/18, 18/22, 12/16 | 80% / 85% / 85% | 各自的错误分支 |
| `Ledger` | ledger.py | 219/260 | 85% | 锁等待超时、写失败降级、tidy 分支、过期 running 的 target 检查 |

**规则**：
- 用确定性 stub（patch `run_herdr` / `subprocess.Popen` / `time.sleep` / 时钟），不启动真实 agent、不依赖真实 herdr；每个新测试模块装离线守卫（`install_offline_guard`），命名 `tests/hao/test_gap_*.py`。
- 每个测试断言行为（返回码、JSON、herdr 调用序列、文件系统结果），不是"跑过不报错"。
- 正常环境与 herdr 不可达两种模式全过；集成冒烟通过。
- **变异自检**（5 处关键行为：门槛退出码、restore 部分失败、`run_herdr` 超时、abort 授权、`safe_read` 路径穿越）：临时改坏实现（例如翻转判断），确认对应测试失败，再恢复；简报里列出试过的变异。
- 不改实现代码（B 是纯补测试）；若发现实现确实有 bug，停下来报告 quill，不要顺手改。
- 更新 `hao/README.md` 里的单元测试数量。

**提交**：`test(hao): close the largest unit-test gaps`（可按主题拆多个提交）

---

## C. 真机场景套件 `tests/hao/live/`（第二轮）

目标：把本会话验证过的约 50 个真机场景固化成**可选运行**的套件，防止回归。详细规格在第一轮验收后补全到本节；要点：

- 入口 `python3 tests/hao/live/run_live.py [--filter NAME] [--quick]`，需要 `HERDR_ENV=1`；不进默认单元测试发现范围（目录无 `__init__.py`，文件名不以 `test_` 开头以免被守卫元测试扫描）。
- 只操作自己创建的一次性实例（后台标签页 + 一次性 pi），`finally` 里关标签页、`hao clean --all`，并断言零残留。
- 每个场景一个函数，记录 PASS/FAIL/SKIP 与细节，退出码非零表示有失败；`--quick` 跳过慢场景。
- 所有 herdr / hao 调用有超时上限；禁止 `pkill -f` / `killall`；不向其它 pane 发送按键。

## 约束

- 不改哨兵匹配器与 tail 提取逻辑。
- 自包含，入口仍是 `python3 scripts/hao`，零外部依赖。
- 禁止 `pkill -f` / `killall`；测试不启动真实 agent（单元测试）；真机验收由 quill 做。
