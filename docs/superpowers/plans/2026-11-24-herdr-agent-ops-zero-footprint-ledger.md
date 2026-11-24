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
