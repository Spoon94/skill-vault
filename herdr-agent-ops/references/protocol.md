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

- **canonical 完成**：peer 在最终 assistant 消息最后一行打印 `HAO_DONE <token>`。Bash tool stdout 不进 pane snapshot，`hao done` 经 tool 执行时 stdout 不可靠，但台账/wake 副作用可用。
- **防回显**：token 拆分两段，prompt 不含完整 token；`[TASK <shortid>]` 用独立短 id。
- **匹配器**：server 侧 `pane wait-output --regex` 容忍前缀（TUI 缩进/⏺/Markdown 引用/列表/编号/backtick/bold/标题/表格/冒号）与尾部标点/边框；要求 HAO_DONE 与 token 邻接，token-only 引用不匹配（无 busy-loop）。
- **完成确认**：必须有任务级证据（哨兵 `HAO_DONE <token>` 或台账 `status=done`），可降级（台账不可写时哨兵仍可确认）。`state_change_seq` 仅活动门槛，不作完成信号。
- **活动门槛**：相对 submit_state 的 working/blocked transition，或 submit_seq + 短窗口 final idle/done（fast coverage）。
- **长等待兜底**：`herdr agent wait --until idle/done/blocked`（server 侧），短超时循环兼顾 cancel；`--timeout 0` 翻译为省略 `--timeout`。
- **终态模型**：任何 wait 成功即写 `status=done`（含 matched_line 或 result_path）；TTL 按 updated 不清活跃 running，orphan running（无心跳超 TTL）才清；terminal 记录保留至 TTL，可重复 wait/result。

## JSON schema（各命令 --json）

- `hao suggest --json`：`{"group": str, "reason": str, "candidates": [name, ...]}`
- `hao ask`（异步）：`{"token": str}`
- `hao wait`：`{"status": "done", "result_path": str?, "summary": str?, "matched_line": str?}`
- `hao list`：`{"panes": [{"pane_id", "label", "agent", "cwd"}]}`
- `hao status`：`{"agent": {...}}` 或 shell/pane 信息。
- **`hao done` 例外**：哨兵走 **stdout 最后一行**（`HAO_DONE <token>`），JSON 结果走 **stderr**（避免污染哨兵行）。
