# hao wait 导致被指挥 agent 界面滚动：修复计划

> 分工：quill 设计并验收，verse 实施。分支 `fix/hao-wait-scroll`（基于 main 00da06b，即 PR #10 合并后）。
> 要求（用户原话）：**既要保证之前的功能正常运行，又要修复 pi 的这个 bug。**

## 问题

使用 hao 派活后，被指挥 agent（pi 等 TUI agent）的 herdr pane 持续上下滚动，直到 `hao wait` 结束。用户抓到的现场：一个忘了加 `--timeout` 的 `hao wait`（默认 1800s）每秒轮询读对方 pane，导致对方界面一直跳。

## 复现证据（quill 实测，2026-11-27）

一次性 pi 实例，先完成一个短任务（屏幕上留下旧 `HAO_DONE`），再异步派 `sleep 120` 让其保持 working，随后 `hao wait <pane> --token <B>`（不带 `--timeout`）：

- 以 0.5s 间隔对 pi 的 visible 视口采样 90 次（45s），**89 次**顶部正文行变成不同的历史内容（持续滚动）。
- 无 wait 的对照：6 次采样仅 1 次变化。
- **done 状态的 pi**：任何 `--lines`（15/30/45/80/200）的读取都不翻屏（0 变化）。
- **working 但静止（sleep 执行期、无输出）的 pi**：`agent get`、`agent wait`、`read --lines 200/30`、`wait-output` 均不翻屏（0 变化）。
- 结论：**滚动发生在 peer 活跃输出（TUI 渲染中）时**，herdr 的 `pane read` / `pane wait-output` 为收集内容与 TUI 渲染相互干扰，把视口翻到不同位置；done/静止时不翻屏。

## 机制：等待循环里的高频 pane 内容读取

`hao/scripts/hao` 的 `_wait_sentinel`：

- **fast path（前 ~30s）**：每轮 `agent get` + `pane wait-output --regex … --timeout 1000`；W2 修复后，若 wait-output 命中的是**别的任务**的哨兵（stale），同轮再 `pane read --lines 200` 重扫。working 且屏幕有旧哨兵时，每秒都有 wait-output + read 200。
- **backstop（>30s）**：peer idle/done 时 `agent wait` 立即返回，随后 `pane read --lines 200` + `sleep 0.5`，即每 0.5s 一次大读取。

`pane read` / `pane wait-output` 在 peer 活跃输出时翻屏，于是 peer 界面持续滚动。`_wait_lifecycle` 的 backstop 有同样的 read 200。

## 修复方案

原则：**peer working（活跃输出）时，把 pane 内容读取降到低频兜底，用不读 pane 内容的 `agent get` / `agent wait` 等状态变化来衔接；peer 状态稳定后恢复正常扫描。** 不改哨兵匹配器、不改完成判定语义、不改 JSON/退出码契约。

### 改动点

1. **fast path 按状态分流**（`_wait_sentinel`）：
   - `last_status == "working"`：本轮**不做** `pane wait-output`，也不做 stale 的 `read 200`。改用 `agent wait --until idle --until done --until blocked --timeout 2000` 等状态变化（不读 pane 内容、不翻屏），并保留每轮的台账/心跳检查。仅当距上次 pane 扫描 ≥ `WORKING_SCAN_INTERVAL`（默认 **10s**）时，才做一次兜底 pane 扫描（wait-output；若 stale 再 read 200），防止 peer 一直 working 却早已打印哨兵的情况漏检。
   - `last_status != "working"`（idle/done/blocked/unknown）：保持现有行为（wait-output + stale 重扫），保证 peer 收尾后能立即读到哨兵。
   - 记录 `last_pane_scan` 时间戳用于兜底降频；`_confirm_sentinel`、`_finish_sentinel`、W1 的 herdr 超时处理、W2 的 stale 判定逻辑都不变。
2. **backstop 降频**：`_wait_sentinel` 与 `_wait_lifecycle` 中，peer 已 settle（idle/done）时的 `pane read --lines 200` 之后 `time.sleep(0.5)` 改为 `time.sleep(2)`（read 之后无命中时的间隔），避免 settle 后还每 0.5s 大读取。
3. 常量集中：新增 `WORKING_SCAN_INTERVAL = 10` 与 `SETTLED_SCAN_INTERVAL = 2`，便于调整与测试。

### 为什么这样既能修滚动又保功能

- peer 活跃输出时，绝大多数等待时间由 `agent wait`（不翻屏）占据，pane 扫描降到每 10s 一次 → 滚动从每 0.5s 降到每 10s，肉眼基本不可见。
- peer 打印哨兵后状态转 idle/done，分流到非 working 分支，立即正常扫描，哨兵检测不被拖延；即使 peer 一直 working，也有每 10s 的兜底扫描，最迟 ~10s 检测到。
- 哨兵匹配器、`tail` 提取、台账/唤醒、退出码、JSON 字段全部不动。

## 验收

1. **单元测试**：正常环境与 herdr 不可达（PATH 上 `exit 1` 的 herdr 替身）两种模式全过；集成冒烟通过。新增/调整测试：working 时 fast path 不调用 `pane wait-output`（用 stub 统计），兜底扫描按 `WORKING_SCAN_INTERVAL` 触发；非 working 分支行为不变。所有测试模块继续装离线守卫。
2. **真机（quill 做）**：一次性 pi，先完成短任务留旧哨兵，再派 `sleep 120` 使其 working，`hao wait` 不带 `--timeout`，45s 采样视口滚动次数 **< 5 次**（修复前 89 次）。
3. **功能回归（quill 做）**：真机派一个普通任务（短）和一个长任务（sleep 75），均能正常完成并带回结果（哨兵或台账）；连续两个 `--text-only` 任务，第二个仍能及时返回。
4. 验收通过后由 quill 提 PR，**不合并**（用户合并）。

## 约束

- 不改 `_token_matches`、`_join_wrapped_sentinels`、`_confirm_sentinel`、`SENTINEL_RE`、`_PREFIX_LINE_RE`、`_HEX_CONT_RE`。
- 测试里不启动真实 agent、不发送按键（用 stub 与 `HAO_STATE_DIR` 临时目录）；真机验收由 quill 用一次性实例做。
- 禁止 `pkill -f` / `killall`；hao 只留在 skill 目录内；不改其它项目。
