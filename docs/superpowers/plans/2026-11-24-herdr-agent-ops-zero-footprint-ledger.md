# herdr-agent-ops 零残留台账（Z1–Z6）

> 用户要求（2026-11-24）：「用完需要清理，这个是需要改的，能不能不用文件？」
> 设计结论：完全不用文件不可行（`ask` / 对端 `done` / `wait` 是三个独立短命进程，常需跨 agent），但可以做到**零残留**——不用不建、用完即删、空了就收，且不落在用户主目录。

## 现状问题

- 台账固定在 `~/.local/state/hao/tasks/`，留在用户主目录
- 所有任务清掉后目录与 `.cleanup.lock` 仍然存在
- `doctor` 等只读命令会创建 `.cleanup.lock`
- 终态记录默认保留 24h，即使结果早已被取走

## 设计

### Z1 位置：系统临时目录
- `HAO_STATE_DIR` 若设置则用它（测试隔离也用它，取代现有的 `XDG_STATE_HOME`）。
- 否则：Linux 且设置了 `XDG_RUNTIME_DIR` → `$XDG_RUNTIME_DIR/hao/tasks`（tmpfs，随登录会话消失）；其他情况 → `tempfile.gettempdir()/hao-<uid>/tasks`（macOS 为用户级 `$TMPDIR`，系统定期清理；回退 `/tmp`）。
- 目录权限 0700。台账是运行时状态，重启/登出后消失是预期行为（任务本身也活不过 herdr 重启）。

### Z2 不用不建
- `status` / `list` / `doctor` / `restore` / `suggest` / `name` / `clear` / `clean --dry-run`，以及对不存在任务的 `wait` / `cancel` / `result` / `done`：**不创建任何文件或目录**。
- 只有 `ask` 派发、以及对已存在记录的心跳/写入才会落盘。

### Z3 用完即删
- `wait` 取到 done（sentinel / lifecycle）：返回体已带 `summary` / `matched_line`，随即删除该记录及其锁文件。
- `wait` 取到 cancelled（rc=10）：删除该 tombstone 及其锁文件（等待方已知情）。
- file 模式 done：保留记录与结果文件，直到 `hao result <sid>` 读取完（随即删除记录、锁、结果目录）。
- `cancel` / `abort` 留下 tombstone，直到被某个 `wait` 观察到（→ 删除）或被 TTL 清理；此间迟到的 `hao done` 仍 rc=6。
- 两个等待方同时等同一个任务：先取走的一方删除记录，后一方得到 rc=3「task record already consumed」。文档注明这是限制。

### Z4 空了就收
- 任何一次删除之后执行 tidy：回收无主锁文件与孤儿结果目录；若 `tasks/` 已无记录，则删除 `.cleanup.lock`、`tasks/` 及其空的父目录 `hao/`。**全部任务结束后不留任何目录。**
- 清理不再使用 `.cleanup.lock` 文件：对 `tasks` 目录本身 `open` + `fcntl.flock` 加锁。
- per-record 锁 `<sid>.json.lock` 随记录一并删除。

### Z5 TTL 兜底
- 无人认领的终态记录与孤儿 running 仍按 TTL 清理（默认 24h，`hao clean --ttl` 可调）；系统对临时目录的定期清理是最后一道兜底。
- `doctor` 顺带做 TTL 清理与 tidy，且在无任何状态时**不创建**目录。

### Z6 对端不走岔
- prompt 内嵌的对端命令带上调用方的台账目录：`HAO_STATE_DIR="<dir>" "<python>" "<skill>/scripts/hao" done …`，对端进程环境变量不同也写到调用方读取的同一位置。

## 文档与测试

- README / SKILL.md / protocol.md：删除 `~/.local/state/hao/tasks/` 的表述，改为「运行时临时状态：仅在有任务时存在于系统临时目录，取走即删，目录随之消失；可用 `HAO_STATE_DIR` 指定」。
- 测试：全部改用 `HAO_STATE_DIR` 隔离。新增：只读命令零创建（跑完后父目录下无任何新条目）；consume 即删；cancelled 被观察后删除；file 模式由 `result` 删除；空目录连同父目录一并消失；孤儿锁回收；位置解析的三种回退；对端命令带 `HAO_STATE_DIR`。
- 集成冒烟同样用 `HAO_STATE_DIR` 隔离。

## 验收（Claude）

1. 全新环境依次执行 `doctor` / `status` / `list` / `restore --dry-run` / `suggest` → 临时目录下不存在 `hao*`。
2. 真实任务 `ask --wait` 完成 → 记录与目录全部消失。
3. 异步任务 + `wait` 取结果后同上；`cancel` 后由 `wait` 观察到 rc=10 → 消失。
4. `~/.local/state/hao/` 不再被创建。

---

# 追加（C1–C2）：cancel 如实告知对方仍在运行

## 现象

`hao cancel` 只作废台账、不碰对方（设计如此），但输出不提示这一点。实测中调用方取消后以为对方已停，对方（forge）继续跑完了两个长任务。更糟的是 Z3 规定等待方一观察到 cancelled 就删除 tombstone，此时按提示去 `abort --interrupt` 会得到 rc=3，无法再停止对方。

## 修复

### C1 cancel / abort 的输出如实提示
- `hao cancel <sid>` 与不带 `--interrupt` 的 `hao abort <sid>`：JSON 输出增加 `peer_running`（取消时目标 agent 是否处于 working）；为 true 时增加 `next`：`"<HAO_CMD> abort <sid> --interrupt"`（与 `ask` 的 `next` 字段同一约定），stderr 再输出一行同样内容的提示。文本模式输出同一提示。
- 文档（README 命令面、protocol.md）明确：`cancel` 只是不再等结果，对方继续运行；要对方停下用 `abort --interrupt`。

### C2 取消记录的保留规则
- 取消的 tombstone **不再**在等待方观察到 cancelled 时立即删除。保留到下列任一情况：
  (a) `abort --interrupt` 执行完毕 → 删除；
  (b) 后续 tidy 发现目标 agent 已不处于 working → 删除；
  (c) 取消后超过 1 小时 → 删除；
  (d) `hao clean`。
- tidy 只在会改变状态的命令以及 `doctor` / `clean` 中运行；只读命令不做删除。
- done 记录「取走即删」的规则不变；无记录时目录照旧一并消失。

## 测试
- cancel：目标 working → `peer_running: true` 且 `next` 含 `abort … --interrupt`、stderr 有提示；目标 idle → `peer_running: false` 无 `next`；无 target → 无 `next`。
- 保留规则：cancel → 等待方得到 rc=10 → tombstone 仍在 → `abort --interrupt` 成功 → tombstone 与目录消失；cancel 后目标已不 working → 下一次 tidy 删除；取消超过 1 小时 → `clean` 删除。

## 流程约束（给实施方）
- 测试中需要「工作中的 agent」一律用 stub，不得向任何真实 agent 派发长任务。
- **禁止 `pkill -f`、`killall` 等按名称或模式结束进程**（2026-11-24 的 `pkill -f 'herdr-agent-ops/scripts/hao'` 误杀了其他会话的后台 `hao wait`）；只能按 PID 结束自己启动的进程。
