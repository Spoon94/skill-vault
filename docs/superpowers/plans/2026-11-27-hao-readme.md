# hao README 重写

> 分工：quill 出规格并验收，verse 实施。分支 `docs/hao-readme`，叠在 `fix/hao-sentinel-separator`（PR #13）之上——先合并 PR #13，再合并本分支。只改 `hao/README.md`。

## 为什么要重写

用户指出"README 没有优化"。现状是旧的操作手册上打了补丁：

- **定位还是旧的**：开头讲的是"任务级等待缺失、名字重启即丢、取短名难"，没提分档协作、角色、工作流。
- **目录树是错的**：写着 `scripts/hao` 是单文件，没有列 `scripts/waiting.py`。
- **结构跟着旧工具走**：角色目录的表硬插在命令表和"短别名"之间；"短别名""等待模式"两行挂在"角色目录"标题下。
- **"30 秒上手"教的是旧流程**：取名 → 派活 → 恢复，没有按角色、按档位派活的例子。
- **这轮踩出来的坑一条都没进 README**（散落在 SKILL.md、workflow.md、protocol.md）。
- **"关键约定"是一大段旧的运维细节**，没有按新用户重新组织。

目标：第一次接触的人或 agent 读完 README 就能上手分档协作；每句话都与 CLI 和代码一致。

## 新结构（按此顺序）

1. **标题与定位**（一段，3–5 句）。`hao` 是在 herdr 上做分档多 agent 协作的 CLI，herdr 只是通道。三件事：角色目录（27 个带档位的角色）、按档位派活（简报与默认输出上限随档位收紧，贵模型只在最难处花钱）、任务级等待（等的是"这个任务完成"，不是"对方空闲"）。名字与角色的命名、恢复作为附带能力提一句。
2. **前置条件**。保留现有 6 条，措辞精简。
3. **30 秒上手：按角色派活**。
   - `doctor` 自检 → `name <pane> <name> --role reviewer` → `ask <pane> "…" --wait`，注释里写出返回的 `role` / `tier` / `max_lines`。
   - 长任务：`--wake "$HERDR_PANE_ID"`，收到唤醒后按通知里的命令取结果。
   - 重启后 `restore --dry-run` / `restore`。
   - 一个最小的三档配合示例（规划 → 拆解 → 实施 → 初审 → 终审，每步一行命令），并指向 `references/workflow.md`。
4. **命令面**。表格保留，每条命令的参数列全。短别名一行放在表格后面。
5. **角色目录**。五组表；角色名 7–20 个字符；命名与角色解耦；新增角色只需在 `references/roles.md` 加一行。
6. **按档位派活**。一张表：`top` 精简简报、默认输出 ≤15 行；`mid` 与 `low` 共用完整简报，`mid` ≤40 行，`low` 不限；无角色的目标同 `low`。`--max-lines` 覆盖（`0` 不限，负数 exit 2）。
7. **等待与结果**。
   - 完成证据：台账 `done`，或对方屏幕上的哨兵 `HAO_DONE <token>`。
   - 答复载荷的优先级：`summary`（对方调了 `hao done --summary`）→ 结果文件（file 模式，读进 `tail` 并删除文件）→ `tail`（从对方屏幕提取）。
   - `wait` 返回字段的小表：`status`、`summary`、`tail`、`last_line`、`tail_note`、`matched_line`、`result_path`、`result_consumed`、`role`、`tier`、`max_lines`、`target_cols`。
   - 三种模式各一行、写明适用场景：`sentinel`（默认）；`lifecycle`（以对方的状态序号为活动门槛，派发前会等对方收尾，最多 10 秒）；`file`（对方把结果写进文件，返回时内联在 `tail` 里，文件随即删除）。
   - 超时：默认 1800 秒；exit 4 的错误信息里带 `agent_status` 和下一步提示。
8. **派活前要知道的几件事**。每条一到两行：
   - 对方输入框必须为空，否则没提交的文字会被一起提交或被丢弃。
   - 给垫底角色设短的 `--timeout`；对方干完活却不发完成信号时，`wait` 只在超时返回。
   - 弱模型不一定调用 `hao done`，`summary` 可能为空，这时用 `tail` / `last_line`。
   - 需要审批的、或访问不到 hao 的对方用 `--text-only`。
   - `ask --wait` 返回时对方可能还在 working 一两秒，紧接着派下一个默认模式没问题。
   - 不要省略 `--timeout` 做长时间轮询。
9. **命名与恢复**。名字规则、label 格式 `hao-<name>-<role>`、零注册表、`--role ""` 清除角色、旧 label 的非角色段原样保留、`restore`。
10. **控制命令**。`cancel` / `abort` / `stop` 三者的区别，各一行。
11. **输出契约与退出码**。保留现有内容。
12. **目录**。修正：列出 `scripts/waiting.py`，说明它是等待内核，加载时合并进 `hao` 的命名空间，不是独立模块；同时列出 `references/` 下五个文件各一句话。
13. **测试**。保留现有内容（数字与现状一致）。
14. **从旧版本升级**。保留，挪到靠后。
15. **设计文档、来源**。保留。

现在"关键约定"里的台账细节（取消记录何时回收、过期 running 记录如何判断）各保留一句结论，细节指向 `references/protocol.md`；台账位置的那一条保留（对着 `ledger.py` 的 `state_dir()` 核对：`HAO_STATE_DIR` 可覆盖；Linux 有 `XDG_RUNTIME_DIR` 则用之；否则系统临时目录下 `hao-<uid>/tasks`）。"等待模式"那行并入第 7 节。

## 硬性要求

- **与 CLI 真实面一致**：`build_parser()` 的每个公开 flag 和每个可选位置参数，必须出现在 README 里**对应命令的那一行**（`tests/hao/test_phase_d9.py` 的文档守卫检查全部 flag；quill 验收时还会按"每个命令自己那一行"核对）。对着代码核对每一句事实，不要凭印象写。
- README 代码块里的每一条命令都必须能被解析器接受（quill 会用 `build_parser().parse_args()` 逐条检查）。
- 不重复展开 `SKILL.md` 和 `references/` 里已有的内容，用链接。
- 只改 `hao/README.md`；不改代码、测试和其它文档。
- 全中文正文，命令、flag、字段名保持原文；总长控制在 200 行以内。
- 提交信息：`docs(hao): rewrite the README around tiered collaboration`。

## 验收（quill）

- 文档守卫通过；按命令逐行核对 flag 与可选位置参数；代码块里的命令逐条用解析器检查。
- 通读一遍，对照上面的 15 节；随机抽 10 处事实对着代码核对。
- 单元测试两种模式与集成冒烟不受影响（只改了 README）。
