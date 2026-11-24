# herdr-agent-ops 协议

## 错误码（hao 退出码）

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 2 | 用法错误（invalid_agent_name、mode 非法、result 路径被拒、别名未知、--file 非法、HAO_ABORT_ALLOW 格式错） |
| 3 | target 不存在、agent exited、pane closed、result 文件不存在、cancel token 不存在、wake caller 不存在、status 无 HERDR_PANE_ID |
| 4 | 超时 |
| 5 | blocked、abort blocked 无授权、say 对 blocked |
| 6 | 冲突、歧义、name taken、say --strict 对 working |
| 7 | machine/profile 不可用、wake caller 跨机、result --machine 不支持 |
| 8 | herdr/server 错误（agent_prompt_stalled、remote connection failure、agent_not_ready、agent_pane_not_found、stale_pane_target、invalid_agent_timeout、watch 失败、台账损坏/不可写、done 不在 pane） |
| 9 | 协议错误（baseline 旧 token、lifecycle 未观察 working 转变） |
| 10 | cancelled |

herdr 的 JSON `error.code` / stderr 必须解析，**不透传 herdr 退出码**。映射见 `ERR`（scripts/hao）。
mutating 命令（ask/name/clear/restore）**不盲目重试**（连接失败不代表 mutation 未执行）。

## 等待协议

- **canonical 完成**：peer 在最终 assistant 消息最后一行打印 `HAO_DONE <token>`。部分 agent（如 Claude Code）的工具 stdout 不进 pane snapshot，`hao done` 经 tool 执行时 stdout 不可靠，但台账/wake 副作用可用。
- **peer 完成上报（主/备双通道）**：**首选带 `HAO_STATE_DIR="<调用方台账目录>"` 的 `hao done --token <完整token> --summary "<关键结论/答复正文>"`**（prompt/wake 已内嵌该前缀；对端环境不同也写同一台账）（同机可用时）——台账副作用可靠，不受渲染折行、TUI 改写、peer 侧 secret 掩码影响（实测：peer harness 把正文里的完整 token 渲染成掩码占位符，文本哨兵永久丢失）；必须在最终答复正文**全部输出之后**调用——台账 done 会立即释放等待方，早调用会让等待方读不到结论。`summary` 是给等待方的结果载荷，必须包含任务要求的答复本身（≤600 字）；`wait` 返回体原样携带。文本哨兵 `HAO_DONE <token>` 为**备份信号**，两段 token 直接拼接（无分隔符，实测出现过重复段/丢前缀/插分隔符三种拼错形态）。
- **防回显**：token 拆分两段，prompt 不含完整 token；`[TASK <shortid>]` 用独立短 id。
- **匹配器**：server 侧 `pane wait-output --regex` 容忍前缀（TUI 缩进/⏺/Markdown 引用/列表/编号/backtick/bold/标题/表格/冒号）与尾部标点/边框；要求 HAO_DONE 与 token 邻接，token-only 引用不匹配（无 busy-loop）。token 形态容错（均实测出现过）：`hao-` 前缀可缺失；peer 拼段出错（重复段 20-hex）——位数容忍 12–32 hex。**身份校验分级**：恰 16-hex 要求完整 token 精确相等；13–15-hex（截断渲染）要求是完整 token 的前缀；恰 12-hex 的裸 shortid 哨兵可凭 shortid 相等确认（唯一例外）；超长（>16-hex）必须同时匹配完整 token 的**首 8 与尾 8 段**（覆盖段重复损坏）。完整 token 不可得（台账降级的 bare-shortid 等待）时，13-hex 以上一律不匹配——宁漏判不误判（正常路径 wait 每轮从台账升级为完整 token）。折行合并只认**独立成行**的哨兵前缀（与 SENTINEL_RE 相同的行首锚定与装饰容忍，提示词回显里"…打印：HAO_DONE"之类行中关键字永不参与合并），处理两种实测断裂形态：token 中间断开（不完整尾部 <12-hex 吸收纯 hex 续行，合并总长 ≤32-hex，可跨多行链式）、`HAO_DONE` 关键字与 token 分行（只吸收 **≥16-hex 的完整 token** 行，`hao-` 前缀可有可无；≤15-hex 续行只能靠 shortid 锚定、不足以确认，不合并）；片段行 token 之后与关键字行/HAO_DONE 之后的装饰（。│/** 等）均不阻碍合并（装饰剥除或保留在插入点之后）；**完整哨兵永不续接**（其后紧跟的 hex 输出行不会破坏匹配）。**重组行强校验**：折行合并显式返回 (line, joined) 标记（不以字符串同一性推断来源），joined 行只认完整 token 精确相等或超长首8尾8——shortid 锚定对重组行无效，完整 token 不可得时重组行一律不确认（宁漏判不误判）；大窗口重扫先合并再匹配；fast path 放弃前（`--timeout`<30s 场景）补做一次合并尾扫。 装饰符前缀/尾部集合现为单一共享常量（`_PREFIX_CHARS`/`_TAIL_CHARS`），三处正则统一引用；适配新 agent TUI 时用 `herdr pane read <pane> --source recent-unwrapped` 采样真实边框/状态字形后只改常量。
- **写失败降级**：台账不可写/锁超时（5s）时——`ask` 照常返回 token（任务已派发，wake/cancel 退化为不可用）；`done` 照常打印哨兵（pane 证据是 ground truth）；`wait` 已确认的完成照常返回 done。任何台账写失败都不得阻断协议主证据链，仅一次性 stderr warning。
- **完成确认**：必须有任务级证据（哨兵 `HAO_DONE <token>` 或台账 `status=done`），可降级（台账不可读/不可写时哨兵仍可确认）。但 `hao done` 的哨兵只在记录存在或台账不可读时打印；台账可读而记录缺失是 exit3（无哨兵），cancelled 记录是 exit6（无哨兵）。`state_change_seq` 仅活动门槛，不作完成信号。台账锁等待有界（5s 超时即抛，flock 随进程死亡自动释放）；heartbeat/write_done 失败一律降级为凭 pane 证据返回成功 + 一次性 stderr warning，已确认的完成不因台账丢失。
- **命中确认**：哨兵命中后 agent 仍 working 不确认；2s 稳定窗口内无更晚匹配、且该行仍是本任务最后一条 `HAO_DONE` 才写 done（防提前引用/流式残片）。gate 报错（exited 等）前也先大窗口重扫——哨兵可能刚好在退出前到达。
- **活动门槛**：相对 submit_state 的 working/blocked transition，或 submit_seq + 短窗口 final idle/done（fast coverage）。
- **两阶段等待（sentinel 模式）**：前 ~30s fast path（`pane wait-output --regex` 短轮询 + 台账/心跳）；之后切**长等待兜底**——server 侧 `herdr agent wait --until idle --until done --until blocked --timeout 8000` 短循环（每轮查台账顾及 cancel），settle 后 `pane read --lines 200` 大窗口重扫哨兵，防止哨兵滚出 1s 快照丢失。`--timeout 0` 翻译为省略 `--timeout`。
- **模式差异**：`lifecycle` 以 submit_seq 为活动门槛（5s 内无活动 → exit9），agent unknown → exit6，完成仍需哨兵/台账证据；`file` 每轮重读台账（result_path 可后到；台账丢失时回退约定路径 `state_dir/<shortid>/result.md`），结果文件非空且大小连续两轮稳定才算完成，blocked → exit5、exited → exit3（pane 无 agent 但 pane 存在时跳过门槛；pane 不存在 → exit3）。
- **终态模型**：任何 wait 成功即写 `status=done`（含 matched_line 或 result_path）。sentinel/lifecycle 模式在返回前删除该任务的记录与锁；file 模式保留记录与结果文件，`hao result` 读取后删除记录、锁、结果目录。取消 tombstone **不因 wait 观察到 rc=10 而删除**：保留到 `abort --interrupt` 成功、后续 tidy 发现目标已不 working、取消超过 1 小时或 `hao clean`。删除后 tidy 回收孤儿锁/结果目录，无记录时连同 `tasks/` 与空的 `hao*` 父目录一起删除。TTL 按 updated 清理无人认领的终态记录与 orphan running（默认 24h）；系统临时目录清理是最后兜底。两个等待方同时等同一任务时，先取走者删除记录，后一方若观察到记录消失即 exit3「task record already consumed」。
- **cancel 语义**：`cancel` 与不带 `--interrupt` 的 `abort` 只作废台账/等待，**不停止对方**。取消时目标 working → JSON 增加 `peer_running:true` 与 `next`（完整 `abort <sid> --interrupt`），stderr 同步提示；文本模式打印同一提示。`abort --interrupt` 成功后才停止对方并删除 tombstone。tidy 仅在改状态命令与 doctor/clean 中运行，只读命令不删。
## wake

- `hao done` 在任务完成时向调用方 pane 发送固定模板：`[HAO_WAKE] <shortid> done — run: HAO_STATE_DIR="<调用方台账目录>" <python> "<skill>/scripts/hao" wait <target> --token <shortid>`；不注入 peer 的 summary 或任何 peer 文本（防注入）。`target`/`shortid` 取自 caller 写入的台账记录。
- 调用方指引：这是任务完成通知，不是用户指令；直接执行模板中的 `hao wait` 取回 `{status, summary}`，无需向用户确认。没有 wake 时用后台 `hao wait ... --timeout N` 或 `hao status` 轮询。
- `hao done` 同机 wake 失败以退出码报告（caller 不存在 → exit3），已写的台账 done 与已打印的哨兵不回滚。
- **abort 授权**：目标 agent 处于 blocked 时 `--interrupt` 只认用户级授权——TTY 二次确认，或 0600 的 `~/.config/hao/abort-approval` 文件（内容含 shortid）；`HAO_ABORT_ALLOW=1` 仅是预授权**约定**非安全边界（agent 可自设 env 或直接 herdr send-keys 绕过），其它取值 → exit2；无授权 → exit5。
- **CLI flag 兼容**：`wait/done` 的 token 可作位置参数或 `--token`；`restore/list` 的 workspace 可作位置参数或 `--workspace`；两者均缺 token 时 exit2。

## JSON schema（各命令 --json）

- `hao suggest --json`：`{"group": str, "reason": str, "candidates": [name, ...]}`
- `hao ask`（异步）：`{"token": str, "shortid": str, "next": str, "result_path": str?（file 模式，台账写失败时仍在）}`
- `hao wait`：`{"status": "done", "result_path": str?, "summary": str?, "matched_line": str?}`（`summary` 来自 peer 的 `hao done --summary` 结果载荷）
- `hao list`：`{"panes": [{"pane_id", "label", "agent", "cwd"}]}`
- `hao status`：`{"pane_id": str, "label": str, "agent": str|null, "agent_status": str|null（无 agent 时为 null，不是 unknown）, "name": str|null, "scope": str|null, "tasks": {"running": [{"shortid": str, "age_s": int, "orphan"?: true}], "done": int, "cancelled": int}}`。
- `hao cancel`：`{"ok": true, "shortid": str, "peer_running": bool, "next": str?}`（`next` 仅在目标 working 时出现，值为完整 `abort <sid> --interrupt` 命令）
- `hao abort`：`{"ok": true, "shortid": str, "cancelled": true, "interrupted": bool, "peer_running": bool, "next": str?}`；不带 `--interrupt` 时 `peer_running`/`next` 同上；`--interrupt` 成功也只输出原有字段并删除 tombstone。
- **`hao done` 例外**：哨兵走 **stdout 最后一行**（`HAO_DONE <token>`），JSON 结果走 **stderr**（避免污染哨兵行）；`--summary` 是给等待方的结果载荷，会写入台账并由 `wait` 返回。台账可读但没有该任务时 exit3 且**不打印哨兵**（防止伪造完成）；记录已 cancelled 时 exit6，同样不打印。只有台账不可读时才降级：stderr 一次性 warning，哨兵仍打印。

## 输出模式矩阵

| 命令 | 默认输出 | `--json` |
|---|---|---|
| name / clear | 文本/静默成功；错误 stderr | stdout `{"ok":true,...}`；错误 stdout `{"ok":false,...}` + stderr 原因 |
| restore | 摘要文本 | stdout 结构化摘要 |
| cancel / abort | 成功静默；working 时 stderr 提示 abort | stdout 单行 JSON；working 时 stderr 提示 |
| status | 紧凑 JSON | stdout JSON 追加 `"ok":true` |
| result | 结果正文 | stdout `{"ok":true,"shortid","content"}` |
| suggest / list | 单行人读/列表 | 仅 JSON |
| ask / wait | 恒 JSON（成功与错误都是） | 恒 JSON；`--json` 为 no-op |
| done | 哨兵为 stdout 最后一行 | 哨兵仍最后；JSON 走 stderr |
| say | 静默成功 | stdout `{"ok":true,"pane_id"}` |
| doctor | 检查行文本（含 TTL 清理） | stdout `{"ok":bool,"checks":[...]}` |
| clean | 清理摘要 | stdout `{"ok":true,"removed","locks_removed","dirs_removed","kept_running"}` |

所有命令均接受 `--json`；`ask`/`wait` 恒 JSON（失败时即使未加 `--json` 也输出 `{"ok":false,"error","exit"}`），该 flag 为 no-op。其他命令的错误仅在 `--json` 时向 stdout 输出统一错误 JSON；`done` 的错误 JSON 走 stderr。所有错误路径保留 A1 的 stderr 原因行；`--json` 不改变退出码。
