# herdr-agent-ops 六维审核与改进方案

> 角色：Claude 负责审核与设计；forge（w2:t1:p9）负责实施与修复。分支 `docs/herdr-agent-team-design`（PR #8）。
> 每阶段：forge 实施 + 补测试 + 提交 + 简报（≤40 行）后 `hao done`；Claude 审 diff + 跑测试 + 实探。

## 审核结论

核心等待/台账/命名正确性经 15 轮复审已 PASS；性能健康（CLI ~84ms/次，names.md 解析 ~10ms）。短板集中在 **agent 友好度与易用性契约层**：错误静默、help 零描述、输出形态不一致、设计稿承诺的若干 flag 未落地。

## 实测证据

```
hao --help                      → 子命令列表零描述
hao wait --help                 → 参数零 help；--token 显示为 TOKEN_OPT（dest 泄漏）
hao result zzzz99999999         → rc=3，stderr 完全静默
hao wait w2:p9 not-a-token      → rc=4（白等到超时）而非 rc=2
hao suggest "审查 PR"           → 人读行 + JSON 行混出（未带 --json）
hao status                      → 透传 herdr 原始 agent_info blob
hao restore --workspace wZZZ    → rc=0 零输出（typo workspace 静默成功）
hao name w2:p9 forge（已带 -ops scope）→ scope 被静默丢弃
12/12 探测的错误路径均无 stderr 输出
```

---

## Phase A — P1 契约修复（agent 可靠使用的前提）

### A1 错误路径必须有 stderr 原因行
- **现状**：所有非零退出静默，agent 只拿到退出码，无法区分 `result` 的 3 是"任务不存在 / 无 result_path / 已过 TTL"。
- **要求**：每个非零退出在 stderr 输出一行 `hao <cmd>: <人类可读原因> (exit N)`。覆盖全部 cmd_* 的 return 分支（用一张 `EXIT_REASON` 表或集中式 `fail(rc, msg)` 辅助函数，避免散落的裸 return）。
- **验收**：`hao result deadbeef000000` → stderr `hao result: task not found (exit 3)`；`hao wait … --timeout 2` 超时 → stderr 含 `timeout after 2s`；`hao name w2:p9 BAD_NAME` → stderr 指明合法格式 `^[a-z]{4,6}$`。成功路径 stdout 契约不变。
- **测试**：每个命令至少 1 个错误路径断言 stderr 内容 + rc。

### A2 `normalize_id` 拒绝非 hex 的伪 shortid
- **现状**：裸 id 走 `[a-z0-9_-]{1,64}` 放行，`not-a-token` 被当 shortid 等到超时。
- **要求**：CLI 边界（`normalize_id`）裸 id 必须是 `^[0-9a-f]{12}$`；完整 token 分支不变（`hao-` + 12–16 hex → 取前 12）。ledger 层 `SHORTID_RE` 保持宽松（测试夹具需要）。
- **验收**：`hao wait w2:p9 not-a-token --timeout 2` → rc=2 + stderr 原因；`hao cancel deadbeef000000` 仍 rc=3（合法 id，不存在）。更新 CLI 路径上使用非 hex 夹具（如 `run1`）的测试。

### A3 `suggest` 输出契约
- **现状**：文本模式多打一行 JSON；人读行有尾随空格。
- **要求**：默认 = 单行人读行（`验证审阅: hawk, lens, prism`）；`--json` = 仅 JSON。两种模式互斥。
- **验收**：`hao suggest "审查 PR"` stdout 恰 1 行且无 JSON；`--json` stdout 可 `json.loads`。

### A4 `status` 输出文档化的紧凑 schema + outstanding 任务
- **现状**：透传 herdr `agent_info`（含 terminal_id/agent_session/revision 等噪声）。
- **要求**：
  ```json
  {"pane_id":"w2:p9","label":"hao-forge-ops","agent":"claude","agent_status":"idle",
   "name":"forge","scope":"ops","tasks":{"running":[{"shortid":"…","age_s":12}],"done":n,"cancelled":n}}
  ```
  `tasks` 扫描台账中 `target == pane` 的记录（running 按 updated 算 age；无心跳 >TTL 的标 `orphan: true`）。无 agent 的 pane 输出 shell 信息 + `agent: null`，rc=0。文本模式打印紧凑多行。
- **验收**：`hao status w2:p9` 输出可 `json.loads` 且键集合固定；protocol.md「JSON schema」同步。

---

## Phase B — P2 易用性与设计稿对齐

### B1 完整 help 文本
- 每个 subcommand：一行 description；每个参数：`help=`；修正 metavar（`--token TOKEN`、`--workspace WORKSPACE`，不暴露 dest 名）；`hao --help` 列出每个子命令的一句话用途；顶层 epilog 给 4 个典型示例 + 「退出码见 references/protocol.md」。
- **验收**：`hao --help` / `hao wait --help` / `hao ask --help` 无一参数缺 help；输出 ≤ 40 行/命令。

### B2 `--json` 全命令面一致
- **现状**：protocol.md 标题「JSON schema（各命令 --json）」，实际仅 suggest/list 有 flag。
- **要求**：`name/clear/restore/cancel/abort/status/result` 加 `--json`（稳定 schema：`{"ok":bool,"…结果字段…}` / 错误时 `{"ok":false,"error":"…","exit":N}` 到 stdout 且 rc 不变）。`ask`（异步）与 `wait` 成功时恒 JSON（现状）；`done` 保持哨兵为 stdout 最后一行，`--json` 时 JSON 走 stderr（现状文档化）。文本模式仍带 A1 的 stderr 错误行。
- **验收**：`hao cancel <sid> --json` 输出单行 JSON；protocol.md 增一张「命令 × 默认输出 × --json 行为」表。

### B3 `name` 幂等保留 scope
- **现状**：对已带 `hao-x-scope` label 的 pane 重跑 `hao name <pane> x` 不带 `--scope` → scope 丢失。
- **要求**：未给 `--scope` 且目标 pane 当前 label 带 hao- scope → 沿用该 scope；显式清除用 `--scope ""`。dry-run 输出标明 `scope=ops (kept)`。
- **验收**：`hao name w2:p9 forge` 两次后 label 仍为 `hao-forge-ops`；`--scope ""` → `hao-forge`。

### B4 `restore` 反馈
- **现状**：空/typo workspace 静默 rc=0。
- **要求**：始终输出摘要：`restored N, skipped M (shell-only K, named L), failed J`；零 hao- pane 时输出 `no hao- panes in workspace W`（rc=0）；`--json` 同信息结构化。
- **验收**：`hao restore --workspace wZZZ --dry-run` 有明确提示行。

### B5 设计稿承诺但未落地的 flag（v33 §3/§4/§8）
| 项 | 规格 | 优先 |
|---|---|---|
| `suggest --custom <name>` | 自定义名过 `^[a-z]{4,6}$` + 保留字/灰色词校验，输出候选 | P2 |
| `ask --strict-ledger` | 台账写失败时报错（非降级 warning） | P2 |
| `result --file <p> --allow-any-path` | 安全根外路径 + warning（用户显式担责） | P2 |
| 台账 `caller` 字段 | ask 记录 `HERDR_PANE_ID` 为 caller（诊断/未来 wake 回退） | P2 |
| `wait_consumed` / `result_consumed` | wait 成功 / result 读取置位（spec 终态模型） | P3 |

### B6 `ask` write-ahead 台账
- **现状**：先发 prompt 后写台账；strict 写失败返回 8 时任务已派出，形成孤儿任务。
- **要求**：先采样 submit_seq/submit_state 并 `write_running`，再 `agent prompt`。strict 写失败 → `_set_error` + exit 8，不派发；非 strict → warning 后派发并返回 token；记录已写但 prompt 失败 → 标 cancelled 并返回 herdr 错误码。
- **验收/测试**：strict 不可写不调用 prompt；非 strict 不可写仍派发并返回 token+warning；prompt 失败台账 status=cancelled。

---

## Phase C — P3 文档与打磨

- **C1 README**：加「前置条件」（herdr ≥0.9.5、`HERDR_ENV=1`、python3）+ 30 秒上手路径（doctor → suggest → name → ask --wait）+ 退出码速查表；修正 suggest 示例输出形态（A3 之后）。
- **C2 SKILL.md**：给 agent 一行输出契约：「结果走 stdout（JSON 或单行文本）；失败原因走 stderr 一行；先看退出码再读 stderr」。
- **C3 启动开销（可选，仅做零风险项）**：`argparse` 延迟导入、非 suggest 命令不触发 names.md 加载。不改单文件结构，不引入 .pyc 打包。目标 ≤ 70ms；达不到不阻塞。

---

## 约束

1. 不动等待循环/匹配器内核（11 轮加固的成果），A1 只包裹其返回点。
2. 每项改动带测试；全程 101 → ≥130 绿；集成冒烟通过。
3. 每阶段一个 conventional commit（`feat(hao): …` / `fix(hao): …`），commit message 引用本文件编号（A1…C3）。
4. 简报格式：每项一行「编号 状态 要点」，末尾测试计数；≤40 行；正文输出完再 `hao done`。


---

## Phase D — end-to-end hardening

### D1 完成协议优先于任务正文
- **问题**：对抗性任务“只回复一个字：好”压过 prompt 内完成协议，peer 只回“好”，不打印哨兵/不调 hao done。
- **要求**：任务正文用 `--- 任务开始 ---` / `--- 任务结束 ---` 包住；完成协议置于任务之后，并声明其不属于任务正文、无论任务要求多少字都必须执行；保持 prompt 不含完整 token。
- **验收**：同一对抗任务 `ask --wait` 能完成（台账 done 或哨兵命中）。

### D2 wait 超时诊断
- **要求**：sentinel/lifecycle 等待记录派发后是否观察到 agent working 及最后状态；超时 stderr 追加诊断，例如未观察到 working 时提示 peer 可能跳过完成协议；观察过则给 last status。不动匹配器。
- **验收**：timeout 消息包含 `agent_status` 与 `never observed working`/`observed working`。

### D3 heartbeat 不造空桩 + 集成隔离
- **要求**：`Ledger.heartbeat` 仅刷新已存在记录，不创建 `{updated}` 空桩；`hao wait` 对不存在 id 纯靠 pane 证据等待。集成测试使用临时 `XDG_STATE_HOME`，不写用户真实台账。
- **验收**：heartbeat 缺失记录返回 None、无 JSON 文件；集成后用户台账不变。


### D4 结果摘要载荷
- **问题**：`ask --wait` 完成返回 `summary:null`，调用方拿不到答复正文。
- **要求**：prompt 要求 peer 调 `hao done --token <完整令牌> --summary "<关键结论/答复正文>"`，summary ≤600 字且包含任务答复本身；wait 返回体经台账携带 summary；protocol/README 同步。
- **验收**：`done --summary` 后 `wait` 返回体 summary 相等。
