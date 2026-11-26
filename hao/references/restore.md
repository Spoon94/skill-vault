# restore 算法

## label 解析

受管 label 形如 `hao-<role>[-<scope>]`，正则 `^hao-([a-z]{4,6})(?:-([a-z0-9][a-z0-9-]{0,11}))?$`。`hao-` 前缀是持久化载体；herdr `session.json` 会保存 label。`hao restore` 只处理该正则匹配的 label，其它 label（如 `yaml`、`atcl`）不碰。

## 持久化口径

- herdr `session.json` 同时保存 `label` 与 `agent_name`；`[session] resume_agents_on_restore=true` 会在 server restart 后恢复受支持 agent（如 Claude）的会话。所以「重启必丢名」不准确——label 是我们控制的、与 agent 生命周期解耦的角色槽位；herdr 的 agent_name/resume 是 best-effort，不作契约。
- 真正需要 label 兜底：agent 退出/被替换、unsupported kind、`resume_agents_on_restore=false`、resume 失败。

## pre-flight

1. **scope 只决定恢复哪些 label**：默认当前 `HERDR_WORKSPACE_ID`；`--workspace W` / `--all` 扩大。绝不默认全局（本机 8 个 workspace，防误伤）。
2. **name 占用检查扫整台 machine**：所有 live agents + 所有 workspace 的 label role（per-machine 唯一）。跨 workspace 同名 → exit 6。
3. 解析 label→role/scope→pane→当前 agent；检测 role 冲突（多 pane 同 role）、live name 已被占、startup pending、stale label（无 agent）、非法 label。

## 不自动选 winner

同 role 多 pane 全部报歧义 exit 6 + 候选列表，要求 `--pick <pane>` 或换代号/scope。workspace/tab/pane 自然序仅用于展示，不用于决定身份（pane_id 是 opaque，字符串排序不可靠）。

## 默认 adopt

对 scope 内 `hao-` pane，把非空但不等价的 agent name 改为 label role（解决「agent start NAME 必填、用别名启动后 restore 跳过」的矛盾）；`--no-adopt` 回到只填无名（注：agent start 必有名，实际只覆盖手动启动的无名 agent）。`--dry-run` 预览；非 `hao-` label 需 `--force`。

## 幂等与部分失败

列出成功/失败/跳过，不留静默半恢复态。处理 `agent name cannot change while startup is pending`：等待/重试/报告。`--dry-run` 只输出将执行的 rename。

## orphan / TTL 清理

- **活跃 waiter**：`hao wait` 短循环每轮刷新 `updated`（heartbeat），running 存活按 updated 新鲜度判定（非 waiter_pid，避免 PID 复用/陈旧）。
- **orphan running**：无活跃 waiter 且 updated 超 TTL（如 async ask 无 waiter + peer 无 hao）→ doctor/TTL 清；活跃 running（有 waiter 心跳）不清。
- **terminal/stale**：status=done/cancelled 且 updated 超 TTL → doctor/TTL 清。
- **写失败降级**：done/heartbeat 写失败（不可写/锁竞争）→ 下轮重试 + warning；台账持续不可写时 doctor 保守跳过 orphan 清理（避免误判活跃 wait）。
- **台账不可读**：result 须 `--target/--pane` 或 `--file` 才能 pane 派生（无 shortid→target 映射），否则 exit3 + warning；status/wait 经 target 解析可 pane 派生。
