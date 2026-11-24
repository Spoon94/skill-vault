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


### D6 非零退出具体原因
- **要求**：所有 `cmd_*` 非零整数 return 必须通过 `fail()` 或紧随 `_set_error`；补齐 name/clear/ask/done/abort/say/doctor 的误导性通用文案；AST 守卫测试防回归。
- **state**：status 无 agent pane 的 `agent_status` 为 null（有 agent 但 unknown 仍为 unknown），protocol 同步。
- **验收**：AST 扫描 0 违规；五类误导文案有具体目标/状态/--force/--wait 提示。

---

# 合并后跟进（M1–M3）：JSON 契约与 done 语义

PR #8 合并后，对全部子命令做了一次系统性的 `--json` stdout 扫描（断言 stdout 为空或恰好一个 JSON 值），并用一次性 pi 实例补测了 `restore` 非 dry-run 与 `abort --interrupt` 成功路径（均通过）。扫描发现三处：

| # | 现象 | 违反的约定 |
|---|---|---|
| M1 | `hao abort <sid> --interrupt --json` 输出**两行** JSON（内部 `cmd_cancel` 一行 + abort 自己一行），`json.loads(stdout)` 报 `Extra data` | `--json` 输出单个 JSON 值 |
| M2 | `ask` / `wait` 出错时 stdout 为空（仅 stderr 原因行） | protocol.md 输出矩阵：ask/wait **恒 JSON** |
| M3 | `hao done <不存在的任务 id>` 返回 0、打印哨兵并**凭空创建**一条 done 记录 | 设计稿：「TTL 删后 exit3」——记录不存在即 exit 3 |

## 修复项

### M1 `abort --interrupt --json` 单行 JSON
- 中间的 cancel 不再向 stdout 打印；最终只输出一行：`{"ok":true,"shortid":"…","cancelled":true,"interrupted":true}`（失败时 `{"ok":false,"error":"…","exit":N}`）。

### M2 `ask` / `wait` 出错也输出 JSON
- 非零退出时 stdout 同样输出 `{"ok":false,"error":"<与 stderr 相同的原因>","exit":N}`，stderr 原因行与退出码不变。「恒 JSON」在成功与失败两种情况下都成立。

### M3 `hao done` 对不存在的任务返回 3
- 台账**可读**且该 id 无记录（从未派发或已被 TTL 清理）→ 不创建记录、不打印哨兵，stderr `hao done: task <id> not found (exit 3)`。
- 台账**不可读**（降级）→ 维持现状：打印哨兵 + 一次性 warning。
- 对已存在的 done 记录重复 done 仍为幂等 rc=0；对 cancelled 仍 rc=6。

### 守卫测试
- 遍历所有子命令的成功与错误路径（stub `run_herdr`），断言带 `--json`（ask/wait 恒 JSON）时 stdout 为空或恰好一个 JSON 值；`done` 除外（其 stdout 最后一行是哨兵，JSON 走 stderr）。
- M3 三种情形各有断言：无记录且可读 → 3 且台账无新文件；不可读 → 降级；已有 done → 0。

## 验收（Claude）
- 重跑系统性 stdout 扫描：16 条命令全部为「恰好一个 JSON」或（done）按文档例外。
- `hao done <不存在的 12-hex>` → rc=3，台账文件数不变。

---

# 追加（R1–R3）：直接控制对方 agent + 窄 pane 警告

## 背景

用户看到 forge 持续刷屏，要求「控制它、把进程杀掉」。核查后并没有失控进程（forge 空闲、无子进程、屏幕 22 秒内无变化），但暴露两个缺口：

1. **没有任务记录时，hao 无法让一个 agent 停下当前这一轮**。唯一的办法是 `abort <sid> --interrupt`，而它依赖任务记录；今天这种情形只能手写原生 `herdr agent send-keys`。
2. **窄 pane 不提示**。本次 forge 的 pane 只有 25 列。窄 pane 既让任何输出看起来像疯狂滚动，也是此前哨兵连续失配（关键字被拆行、token 被折断，r7–r13）的根源，但派发时没有任何提醒。

## R1 `hao stop <target>`：让 agent 停下当前这一轮

- 语义：向目标 agent 发送 `esc` → `ctrl+c`，不依赖任务记录，不读写台账。
- 守卫（安全优先，宁可不发也不误发）：
  | 目标状态 | 行为 |
  |---|---|
  | working | 发送 `esc`、`ctrl+c`；回读状态写入输出 |
  | idle / done / exited / closed | **不发按键**（对空闲的 TUI 发 `ctrl+c` 可能触发退出），exit 0，输出 `already idle` |
  | blocked | 与 `abort --interrupt` 相同的用户级授权：TTY 确认，或 0600 的 `~/.config/hao/abort-approval` 文件内容含该 pane id；无授权 exit 5 |
  | unknown | 不发按键，exit 9，提示 |
  | pane 无 agent | exit 3，不发按键 |
- flag：`--dry-run`、`--json`、`--machine`。JSON：`{"ok":true,"pane_id":"…","agent_status_before":"working","sent":["esc","ctrl+c"],"agent_status_after":…}`；already idle 时 `sent: []`。
- 文档（README / SKILL.md / protocol.md / 顶层 help）写清与 abort 的区别：`abort <sid> --interrupt` = 作废任务并停对方；`stop` = 只停当前这一轮。

## R2 窄 pane 警告

- `ask`：解析目标 pane 后取 `herdr pane layout --pane <id>` 中该 pane 的宽度；小于 40 列 → stderr 输出一行警告（不阻塞、不改退出码）：对方 TUI 会折断每一行、文本哨兵可能无法识别、台账通道不受影响、建议加宽 pane。JSON 输出增加 `target_cols`。取不到布局时静默跳过。
- `doctor`：`HERDR_PANE_ID` 可用时报告当前 pane 宽度（小于 40 列记为 warn），取不到则跳过；不创建任何文件。
- 测试（stub 布局）：窄 → 有警告且有 `target_cols`；宽 → 无警告；布局获取失败 → 静默。

## R3 验收（Claude）

一次性实例放在**后台标签页**，不再挤用户当前标签页。

- `hao stop`：working 的 agent → 停下；idle → 不发按键、rc=0；无 agent 的 pane → rc=3；blocked → 无授权 rc=5、有 0600 授权文件 rc=0（若能人为制造 blocked 状态）。
- `ask` 对小于 40 列的 pane 给出警告，对宽 pane 不给。

## 追加（R4–R6）：验收与真实使用中带出的三处

### R4 `agent_status_after` 读得太早
- 现象：`hao stop`（以及 `abort --interrupt`）发出按键后立刻回读状态，herdr 尚未更新，输出仍是 `working` / `blocked`，agent 读到会以为没停成功。
- 修复：发送后每 0.3s 轮询一次，直到状态相对按键前发生变化或满 3s；输出最后观察到的 `agent_status_after`。3s 内未变化时 stderr 追加一句「状态 3s 内未变化，对方可能没有响应」。

### R5 清理不得删除对方仍在工作的 running 记录
- 现象：真实使用中，异步 + 唤醒的任务从派发起就没有等待方、也就没有心跳（实测一条任务 34 分钟无更新，对方仍在工作）。按现有 TTL 规则（running 且无心跳超过 24h 即清），超过 24h 的长任务其记录会在对方完成前被 `doctor` / `clean` 清掉，之后对方的 `hao done` 得到 exit 3、唤醒也不会发出，结果丢失。
- 修复：`clean` / `doctor` / tidy 在删除 running 记录前检查其 target 的 agent 状态；对方仍 working 或 blocked 时**保留**该记录（不计入可清理）。台账不可读等异常情况维持原有保守行为。

### R6 升级说明
- 旧版本（PR #9 之前）的台账在 `~/.local/state/hao/tasks/`，新版本默认在系统临时目录。升级时若有旧版本派出、尚未取走的任务，用 `HAO_STATE_DIR=~/.local/state/hao/tasks` 运行 `hao wait` 即可读取。
- README 增加一小节「从旧版本升级」写明这一点。

## 验收（Claude）
- R4：对工作中的一次性 agent 执行 `stop`，输出中的 `agent_status_after` 为按键后的新状态。
- R5：构造 running 记录且其 target 为 working，`hao clean --all` 不删除；target 不 working 时按原规则删除。

## 追加（R7）：目标 pane 已不存在的过期记录永远删不掉

### 现象（验收 R5 时实测）
- 对一个已关闭的目标 pane，`current_state()` 返回 `'unknown'`。
- R5 的 `_record_peer_active` 把 `unknown` 视为「对方可能仍在工作」而保留记录。
- 结果：目标 pane 或 agent 已不存在的过期 running 记录，`hao clean --ttl 0`、`--all`、`doctor` 都删不掉，记录与锁文件永久残留。一次性 pane 关闭、agent 退出、herdr 重启后 pane 编号变化都会触发，违背零残留。

### 修复
- `_record_peer_active` 区分「对方不存在」与「状态读不到」：
  - herdr 返回 `pane_not_found` / `agent_not_found`（或 pane 上已无 agent）→ 视为不活跃，过期后可删除；
  - agent 存在且状态为 `working` / `blocked` → 保留；
  - agent 存在且状态为 `unknown` → 保留（保守）；
  - 其他错误（herdr 不可达等）→ 保留（保守）。
- `hao stop` / `abort --interrupt` 的守卫不变（unknown 一律不发按键）。

### 测试
- 过期 running 记录 + 目标 pane 不存在 → `clean --ttl 0` 删除；
- 过期 running 记录 + 目标 pane 存在但无 agent → 删除；
- 过期 running 记录 + 目标 agent working → 保留；
- 过期 running 记录 + agent 状态 unknown → 保留；
- 过期 running 记录 + herdr 报其他错误 → 保留。

## 追加（R8–R9）：真实使用中暴露的两处

### R8 用 agent 名字作 target 时没有被解析成 pane id
- 现象：`hao ask verse …` 可以送达（herdr 自己认得 agent 名字），但 `resolve_target("verse")` 原样返回名字，于是所有依赖 pane id 的功能对名字目标静默失效：窄 pane 警告不触发、输出里 `target_cols` 为 null、台账记录的 `target` 存的是名字而不是 pane id（`status` 按 pane 列任务时对不上）。help 里明确写着 target 可以是 agent name。
- 原因：`resolve_target` 只按 pane label 和 agent 类型（claude/pi）匹配，不按 herdr 的 agent 名字匹配。
- 修复：`resolve_target` 在常规匹配落空后，用 `herdr agent list`（或 `agent get`）按 `name == target` 解析出 pane id；解析不到才原样返回。解析成功后上述功能全部对名字目标生效。
- 测试：名字 → pane id；label / pane id / `w:t:p` 行为不变；不存在的名字原样返回。

### R9 长等待中执行 `abort --interrupt`，等待方可能得到错误的退出码
- 现象：等待超过 30s 进入兜底阶段后，每轮在 server 侧 `agent wait` 里阻塞最长 8s 才查一次台账；`abort --interrupt` 写入取消记录、发按键，约 3s 后把记录删除。等待方很可能错过取消记录存在的窗口，再查时记录已消失，得到 rc=3「task record already consumed」，而不是 rc=10 cancelled。（实测：快速轮询阶段的等待方得到正确的 rc=10。）
- 修复：`abort --interrupt` 不再立即删除取消记录，改为标记已中断；记录由观察到 cancelled 的等待方删除；tidy 仅在该记录**没有新鲜心跳**（没有活跃等待方）且标记超过 60s 时回收。C2 的规则相应改为「取消的记录保留到被等待方观察到，或对方已不 working，或取消超过 1 小时，或 `clean`；`abort --interrupt` 只标记不删除」。
- 测试：等待方处于兜底阶段（用 stub 让首轮即进入兜底，或把 8s 阻塞做成可注入）时执行 `abort --interrupt` → 等待方 rc=10；没有活跃等待方时 60s 后由 tidy 回收。

## 追加（R10–R12）：跨机器错误路径与第三种 agent 的实测

### R10 `--machine` 指向不可用的 machine 时行为不一致
实测对 `--machine no-such-profile-xyz`（herdr 的报错是纯文本 `error: unknown machine '…'`，不是 JSON）：

| 命令 | 现状 | 应为 |
|---|---|---|
| `name … --dry-run` | rc=0，报告成功 | rc=7 |
| `clear … --dry-run` | rc=0，报告成功 | rc=7 |
| `suggest` | **rc=1，Traceback 崩溃** | rc=7 |
| `list` / `restore` / `ask` / `wait` | rc=8 | rc=7 |
| `stop` | rc=3「target not found」 | rc=7 |
| `doctor` | rc=7 | 不变 |

- 修复：`main()` 在解析参数后，对除 `doctor` 外所有带 `--machine` 的命令做一次前置校验（`herdr machine status <m>`）；不可用则统一返回 7 并给出 machine 名与原因，不执行任何后续动作。`herdr_error_rc` 同时识别纯文本的 `unknown machine`。`doctor` 保持自己的报告形式。
- 健壮性：任何 `json.loads(out)` 之前必须检查 `run_herdr` 的返回码；herdr 不可达或返回非 JSON 时返回 8 并给出原因，不得抛出 Traceback（`suggest` 的崩溃即由此而来）。
- 测试：stub `run_herdr` 模拟「未知 machine」与「herdr 不可达」两种失败，遍历所有带 `--machine` 的命令与 `suggest` / `list` / `restore` / `name`，断言退出码正确、无异常、stdout 恰好一个 JSON、且没有派发或写台账。

### R11 对方从未响应时尽早提醒
- 现象：刚启动的 agent 尚未初始化完时，`herdr agent prompt` 返回成功但 TUI 丢弃了输入（qodercli 实测）。`wait` 要等满整个超时才报告「never observed working」。
- 修复：等待循环在派发后约 15s 内，若对方状态始终未离开 idle/done，且没有任何台账或哨兵证据，输出一次 stderr 警告：「对方在派发 15s 后仍无反应，可能没有收到 prompt（例如它还在启动中）；可用 herdr pane read <pane> 查看」。**只警告，不失败**（对方状态不可检测的 agent 仍可能在工作）。状态为 unknown 时不发此警告。
- 测试：stub 状态恒为 idle → 15s 左右出现一次警告且等待继续；状态变为 working → 无警告。

### R12 需要人工审批才能执行命令的 agent 会被 `hao done` 卡住
- 现象：qodercli 默认权限模式下，peer 执行 prompt 里给出的 `hao done …` 命令时会弹出「Allow this command to run?」，于是 blocked，台账主通道用不了（实测）。
- 修复：build_prompt 的首选上报一句改为明确包含这种情况：「若无法执行该命令，或执行它需要向用户申请审批，**不要请求审批**，直接只打印备份信号。」对方因此走文本哨兵通道完成。
- protocol.md 记录：需要审批的 agent 默认走备份通道（拿不到 summary）；用户可为其放行该命令或使用免审批模式以启用台账通道（实测 qodercli 以 `--permission-mode bypass_permissions` 启动并等其初始化完成后，13s 经台账完成）。

### 实测记录（2026-11-25）
- pi、Claude Code、qodercli：端到端通过。agy：本机未登录，无法测试。
- 跨机器 `--machine`：本机无 SSH machine，端到端无法验证；调用点传递经静态审计完整，错误路径由 R10 覆盖。
