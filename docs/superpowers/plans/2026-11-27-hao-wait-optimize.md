# hao wait 优化：合并等待循环 + 答复载荷链 + file 取走即删

> 分工：quill 设计并验收，verse 实施。分支 `refactor/hao-waiting-module`（含 PR #12 的拆分，waiting.py 已独立）。
> 用户已认可方案。前置：PR #12 的拆分已在本分支。

## 目标

1. **合并 `_wait_sentinel` 与 `_wait_lifecycle` 的重复等待逻辑**（行为不变，纯重构）。
2. **答复载荷改为 `summary` → `result.md` → `tail` 的优先级链**，让 file 成为能写文件对端的首选答复通道。
3. **file 模式返回即读入 JSON 并删除结果文件**（取走即删，零残留）。
4. **tail 提取保留为不能写文件对端的兜底**（不简化，保证答复质量）。

## 设计

### A. 合并等待循环（行为不变）

`_wait_sentinel`（~146 行）与 `_wait_lifecycle`（~115 行）里，台账轮询、agent 状态门槛、backstop、超时处理、`response_warned`、`_finish_sentinel`/`_finish_done` 几乎重复。合并为 `_wait_unified(pane, sid, token, timeout, machine, no_agent, accept_unknown, mode)`：

- **共享**：`_wait_round_rec`、`_wait_common_check`、`_agent_status_gate`、`_sentinel_scan_tail`、`_confirm_sentinel`、`_finish_sentinel`、`_wait_timeout`、`_maybe_warn_unresponsive`。
- **按 `mode` 区分**的仅是 fast path 找哨兵的方式：sentinel 用 `pane wait-output`，lifecycle 用 `submit_seq` 活动门槛。
- fast path / backstop 统一为一套逻辑 + 参数化扫描节奏：**working 时 `agent wait` + 每 `WORKING_SCAN_INTERVAL`(10s) 兜底扫描；非 working 时正常扫描**（保留 PR #11 的滚动修复与 W1 的 herdr 超时处理）。
- `_wait_file` 保持独立（文件模式逻辑不同）。
- 效果：约省 100 行重复代码，并消除“改一处漏另一处”的回归风险（R13、滚动修复都曾要改两个循环）。

### B. 答复载荷链

`wait`/`ask --wait` 返回结果时，按优先级取答复载荷：

1. **台账 `summary`**：对端执行了 `hao done --summary`。
2. **`result.md` 文件**：对端写了结果文件 → 读出内容放进 `tail` 字段，**删除文件与记录**。
3. **`tail` 提取**：对端只打印哨兵 → 用现有 `_tail_from_pane_text` 从屏幕抠答复（兜底）。

对端做了什么就取什么，不要求对端选择特定方式；`summary` 仍仅来自台账。

### C. file 模式取走即删（行为变更）

`--mode file` 现状是“返回后保留结果文件，靠 `hao result` 再读才删”。改为：

- 对端写 `result.md`；wait 检测到文件非空且大小连续两轮稳定后，**读出内容放进 `tail` 字段**，**删除结果文件、任务记录、锁与结果目录**（空了连 `tasks/` 一起删）。
- 返回 JSON 直接带答复内容（`tail`），调用方无需再读文件。
- `result_path` 字段保留（原路径，标注已读取并删除）。
- 异步（`--wake`）：wake 消息里的 `hao result` 命令完成“读内容 + 删除”。

### D. tail 提取保留为兜底

`_tail_from_pane_text`、`_normalize_for_match`、`_strip_tui_line`、`_prompt_end_line`、`_is_harness_noise` **保留现有实现，不简化**，作为不能写文件对端的兜底。tail 不再是主路径（主路径是 summary 与 file）。

## 验收

- **测试**：372 个单元测试在正常环境与 herdr 不可达两种模式全过（必要时更新 file/载荷相关测试以反映新行为；核心完成判定、哨兵匹配、tail 提取逻辑不变）；集成冒烟通过。
- **真机功能回归（quill）**：默认模式短任务、长任务（sleep 75）、两个 text-only 任务、tier 分档、file 模式派任务，全部正常。
- **文件清理验证（quill）**：file 模式返回后，`$TMPDIR/hao-<uid>/tasks` 下的结果文件、记录、锁、结果目录全部删除，零残留。
- **性能**：加载/等待行为无退化。

## 约束

- 不改哨兵匹配器（`_token_matches`、`_join_wrapped_sentinels`、`SENTINEL_RE`、`_PREFIX_LINE_RE`、`_HEX_CONT_RE`）。
- tail 提取逻辑不简化（保留现有实现作为兜底）。
- 自包含，入口仍是 `python3 scripts/hao`，零外部依赖。
- 禁止 `pkill -f`/`killall`；测试不启动真实 agent（用 stub + `HAO_STATE_DIR` 临时目录）；真机验收由 quill 做。
