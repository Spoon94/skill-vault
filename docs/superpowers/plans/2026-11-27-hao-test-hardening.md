# hao 测试加固：lifecycle 派发门槛 + 补单元测试缺口 + 真机场景套件

> 分工：quill 设计并验收，verse 实施。分支 `refactor/hao-waiting-module`（PR #12，尚未合并）。
> 用户要求三项都做。分两轮派发：**第一轮 = A + B**（已完成并验收：A = 3bc8054，真机 6/6；B = 849f9b9，485 个测试，覆盖率 93.8%），**第二轮 = C**（规格见第三节）。

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
- 注：`tests/hao/tools/coverage.py` 现在把 docstring 排除在语句之外（它被编译成常量，永远不会产生执行事件）；下表的「当前」一栏是旧口径，验收按新口径：整体 93.8%，18 个函数全部达到下限。

**提交**：`test(hao): close the largest unit-test gaps`（可按主题拆多个提交）

---

## C. 真机场景套件 `tests/hao/live/`（第二轮）

目标：把本会话在真实 herdr + 真实 agent 上验证过的场景固化成**可选运行**的套件，防止回归。单元测试用桩，覆盖不到真实 herdr 的 JSON 形态、真实 TUI 的渲染与状态变化、真实 agent 的配合程度——这个套件补的就是这部分。

### 形态

- 单文件 `tests/hao/live/run_live.py`（仅标准库）+ `tests/hao/live/README.md`（怎么跑、跑什么）。目录不放 `__init__.py`，文件名不以 `test_` 开头：不进默认单元测试发现范围，也不被守卫元测试扫描（它只扫 `tests/hao/test_*.py`）。
- 入口：`python3 tests/hao/live/run_live.py [--filter SUBSTR] [--quick] [--kinds pi,claude] [--list]`
  - `--filter`：只跑名字含该子串的场景；`--quick`：跳过慢场景；`--kinds`：端到端验证的 agent 类型（默认 `pi`）；`--list`：列出场景名后退出。
  - 前置：`HERDR_ENV=1` 且 `HERDR_WORKSPACE_ID` 已设，否则 exit 2 并说明。herdr 不可达也 exit 2。
- 只操作自己创建的一次性实例：后台标签页（`--label hao-live --no-focus`，`--cwd /tmp`）里起一个一次性 agent。`finally` 里关标签页、`hao clean --all`，并断言状态目录不存在。
- 每个场景一个函数，用装饰器登记：`@scenario("name", group="…", slow=False)`；场景内用 `ctx.check(描述, 条件, 细节)` 记录子检查。场景通过 = 所有子检查通过且无异常；异常记为 FAIL 并保留 traceback 末尾。
- 结束时打印每场景 PASS/FAIL/SKIP、耗时、细节和汇总；有 FAIL 则退出码 1。前置不满足（如该 agent 类型起不来）记 SKIP 并说明。
- 所有 herdr / hao 调用都有超时上限；禁止 `pkill -f` / `killall`；不向其它 pane 发送按键；不读写 `~/.local/state/hao`。

### 已验证的接口事实（实现时直接用）

- `herdr tab create --workspace W --cwd /tmp --label L --no-focus` → stdout 最后一行是 JSON，tab id 在 `result.tab_id` 或 `result.tab.tab_id`。
- `herdr pane list --workspace W` → `result.panes[]`，含 `pane_id`、`tab_id`；用 `tab_id` 找到新标签页里的 pane。
- `herdr agent start <name> --kind pi --pane P --timeout 60000` → rc 0；**启动后等约 6 秒**再派活，否则输入可能被丢。
- `herdr agent get P` → `result.agent.agent_status`，取值 idle / working / done / blocked / unknown；另有 `state_change_seq`、`name`。
- `herdr pane read P --source recent-unwrapped --lines N` → 文本；`--source visible` 只取当前视口。
- `herdr agent rename P --clear` 清 agent 名；`herdr pane rename P <label>` 直接设 label；`herdr pane send-text P "…"` 只输入不回车；`herdr tab close <tab>`。
- `hao … --json`：stdout 最后一行是一个 JSON 对象；失败时是 `{"ok":false,"error":…,"exit":N}`，stderr 另有一行文字。
- pi 答一个简单任务约 3–12 秒。它是否调用 `hao done` 不稳定：调用了则 `summary` 有值（台账通道），否则结果在 `tail` / `last_line`（哨兵通道）。断言"答复出现在 summary / tail / last_line 任一"。
- **wait 刚返回时对方还会 working 1.7–2.5 秒**才变 done：场景之间用 `ctx.settle()` 等到 idle/done 再做下一步。

### 场景目录（约 45 个）

**命名与角色**（新实例）
1. `name_sets_label_with_role`：`hao name P moth --role arbiter --json` → rc 0、label `hao-moth-arbiter`、role arbiter、tier top；`herdr pane get` 的 label 一致。
2. `name_keeps_role_when_omitted`：设 developer 后 `hao name P moth --json` → `kept` 为 true，label 仍带角色。
3. `name_empty_role_clears`：`--role ""` → label `hao-moth`、role 为 null、`kept` false；status 的 role/tier 为 null。
4. `name_unknown_role_exits_2`：`--role foo` → rc 2、stderr 含 "reviewer" 和 "arbiter"、无 "Traceback"。
5. `status_shows_role_tier_group`：reviewer → status JSON 的 role/tier/group 为 reviewer / mid / 设计评审；`--text` 输出含 `role: reviewer`。
6. `list_shows_role_and_tier`：`list --json` 中本 pane 的行有 role、tier；文本行含角色和档位两列。
7. `suggest_live_labels`：`hao suggest "review the PR" --live-labels hao-hawk-dev --live-names --json` → 候选列表；`--label-roles` → rc 2。
8. `legacy_label_parses_with_null_tier`：`herdr pane rename P hao-moth-ops` 后 status → role ops、tier null。

**分档与简报**
9. `ask_top_tier`：arbiter，问 "42 加 8 等于多少？只回答数字。" → rc 0、done、tier top、`max_lines` 15，答复含 "50"。
10. `ask_low_tier`：developer → tier low、`max_lines` null。
11. `ask_mid_tier_max_lines_override`：reviewer + `--max-lines 3` → tier mid、`max_lines` 3。
12. `ask_unroled_target`：清除角色后派活 → tier null、`max_lines` null。
13. `ask_rejects_negative_max_lines`：`--max-lines -1` → rc 2、stderr 提到 max-lines，且没有派发（status 的 running 任务数为 0）。
14. `compact_brief_is_shorter`：进程内 `build_prompt` 的 top 简报短于 low；派给 arbiter 后对方 pane 上能读到 "正文不超过 15 行"。
15. `custom_role_from_roles_md`：把 `hao/` 复制到临时目录、在 roles.md 末尾加一行 `reliability-engineer`（mid），用副本的 hao `name --role reliability-engineer` → tier mid；副本 `ask` → tier mid、`max_lines` 40。之后用正式 hao 把角色改回。

**等待内核**
16. `default_task_completes_with_result`：普通任务 → done，答复在 summary / tail / last_line 之一。
17. `long_task_is_waited`（慢）：先执行 `sleep 75` 再回答 → rc 0、done、耗时 > 70 秒。
18. `text_only_back_to_back`：连派两个 `--text-only`，第二个 20 秒内 done。
19. `back_to_back_six_dispatches`（慢）：角色交替连派 6 次，全部 rc 0 且档位正确。
20. `ledger_channel_hao_done`：异步派活拿到 shortid → 直接执行 `hao done --token <sid> --summary "ledger answer"` → `hao wait P --token <sid> --timeout 10 --json` → done、summary 为 "ledger answer"。
21. `lifecycle_mode_back_to_back`：普通任务返回后**立刻** `ask --mode lifecycle --wait` → rc 0、done（A 的修复）；对方空闲时 lifecycle 同样 rc 0。
22. `lifecycle_requires_wait`：`ask --mode lifecycle`（不带 `--wait`）→ rc 2。
23. `timeout_diagnostic_is_actionable`：对空闲的对方 `hao wait P --token <不存在的 12 位 id> --timeout 5 --json` → rc 4，error 含 "no ledger record was ever seen"。
24. `working_peer_is_not_read_at_high_frequency`（慢，滚动回归）：派一个持续输出约 60 秒的任务；把记录 `pane read` / `pane wait-output` 调用的 herdr 包装脚本（先 `exec` 真实 herdr）放到临时目录前置到 PATH，运行 `hao wait` 20 秒，统计调用次数 → ≤ 0.5 次/秒（修复前约 1.28，修复后约 0.15）。
25. `peer_status_transitions`：用 Popen 起 `ask --wait`，轮询 `agent get`，先看到 working、最终 done，ask rc 0。

**file 模式与清理**
26. `file_mode_inline_result`：`ask … --mode file --wait --json` → done、`tail` 非空且含 "42"、`result_consumed` true。
27. `file_mode_zero_residue`：接上，`result_path` 及其目录都不存在，状态目录下没有文件。
28. `stale_record_is_cleaned`：另起一个一次性 pane，异步派一个 `sleep 60`，直接关掉它的标签页 → `hao clean --all --json` 的 removed ≥ 1，状态目录消失。
29. `result_missing_task_exits_3`：`hao result beef11223344 --json` → rc 3。

**控制命令**
30. `cancel_keeps_peer_running`：异步 `sleep 60` → `hao cancel <sid> --json` → ok、`peer_running` true、给出 abort 提示；对方仍在 working。
31. `abort_interrupts`：`hao abort <sid> --interrupt --json` → ok、`interrupted` true，对方数秒内离开 working。
32. `stop_working_peer`：异步 `sleep 60` → `hao stop P --json` → `sent` 非空、之后状态非 working；再 `hao stop P` → `sent` 为空。
33. `stop_dry_run_sends_nothing`：`hao stop P --dry-run --json` → `dry_run` true，状态不变。
34. `say_sends_plain_prompt`：`hao say P "只回答 say-ok" --json` → rc 0，对方 working 后 done，没有产生任务记录。
35. `say_strict_refuses_working`：对方 working 时 `hao say P "x" --strict --json` → rc 6。

**恢复与清除**
36. `restore_after_name_cleared`：reviewer → `herdr agent rename P --clear` → `hao restore --dry-run --pick P` 输出 "would restore name moth (role reviewer) on P"；`hao restore --pick P --json` → restored 1；status 的 name 为 moth、label 为 `hao-moth-reviewer`。
37. `restore_all_dry_run`：`hao restore --all --dry-run --json` → rc 0。
38. `clear_dry_run_changes_nothing`：`hao clear P --dry-run --json` → rc 0，label 不变。
39. `clear_removes_label`：`hao clear P --json` → rc 0，label 为空，status 的 name 为 null。

**只读与诊断**
40. `doctor_reports_environment`：`hao doctor --json` → rc 0。
41. `read_only_commands_create_no_state`：状态目录不存在时依次执行 `list`、`status`、`restore --dry-run`、`suggest`、`clean --dry-run`（都带 `--json`）→ 之后状态目录仍不存在。

**派发与输入框**
42. `draft_in_input_box_is_consumed`：`herdr pane send-text P "UNSENT DRAFT"` 后 `hao ask P "只回答 draft-ok" --wait --json` → done；`pane read --lines 200` 里能找到 "UNSENT DRAFT" 紧挨着 "[TASK"（pi 把草稿拼在任务前面）。

**跨 agent 类型**（`--kinds` 含该类型时才跑）
43. `claude_code_peer_end_to_end`：`herdr agent start <name> --kind claude --pane P -- --dangerously-skip-permissions`，等 45 秒；arbiter 派一个短任务 → done、tier top。`claude` 不在 PATH 时 SKIP。

**收尾**
44. `suite_leaves_zero_residue`：套件结束后状态目录不存在（总是执行，不计入 `--quick` 的跳过）。

`--quick` 跳过标记为慢的场景（17、19、24）。

### 验收（quill 在真机上做）

- `python3 tests/hao/live/run_live.py --list` 列出全部场景。
- `--quick` 全过（约 3 分钟）；完整运行全过（约 7 分钟）；结束后状态目录不存在、没有遗留标签页。
- 默认单元测试（`unittest discover`）不会碰到这个套件；`tests/hao/test_phase_r19.py` 的守卫元测试仍通过。
- 故意制造一个失败（例如临时把某个期望值改错）确认套件会报 FAIL 并返回非零退出码。

---

## 约束

- 不改哨兵匹配器与 tail 提取逻辑。
- 自包含，入口仍是 `python3 scripts/hao`，零外部依赖。
- 禁止 `pkill -f` / `killall`；测试不启动真实 agent（单元测试）；真机验收由 quill 做。
