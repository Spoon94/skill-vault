# hao 工作流

五步协作：**规划 → 拆解 → 实施 → 初审 → 终审**。编排由调用方（通常是 `project-manager`）做；顶级角色只在第 1 步和第 5 步出现。每一步都通过 `hao ask` 派活，用 `--role` 把角色写进 pane label。

命令中的 `python3 scripts/hao` 均相对 SKILL.md 目录；`<pane>` 是 pane id、label 或 agent 名。

派发前确认对方输入框为空：`hao ask` 会消费输入框里已有的未提交文字（pi 把它拼在任务前面一起提交，Claude Code 直接丢弃），草稿会丢失。看到未提交文字时，先请对方用户清空或发送。

## 1. 规划

- **谁来派**：调用方，或已就位的 `project-manager`。
- **派给谁**：`strategist`（方向取舍）、`product-manager`（需求与范围）、`planner`（规格与验收标准）、`architect`（架构与技术设计）。
- **命令**：

  ```bash
  python3 scripts/hao name w2:p9 atlas --role architect
  python3 scripts/hao ask w2:p9 "为 <需求> 给出方案、风险与验收标准" --wait --json
  ```

- **产物怎么交给下一步**：`ask --wait` 返回的 `summary`（≤600 字）可直接放进第 2 步的任务文本；报告较长时用 `--mode file`，返回 JSON 的 `tail` 就是答复内容，结果文件取走即删，无需再读文件；异步场景按 wake 通知取回（记录仍在时 `hao result <shortid>` 也可直接读取并删除）。
- **失败处理**：被审批卡住 → 交用户放行，或改用 `ask --text-only` 重新派发；超时 → `cancel <shortid>` 只停止等待，要停对方用 `abort <shortid> --interrupt` 或 `stop <pane>`。

## 2. 拆解

- **谁来派**：调用方或 `project-manager`。
- **派给谁**：`project-manager`（拆解、排期、派活）；需要跨 agent 路由时用 `orchestrator`，多份结果需要浓缩时用 `synthesizer`。
- **命令**：

  ```bash
  python3 scripts/hao name w2:p10 moss --role project-manager
  python3 scripts/hao ask w2:p10 "把下面的方案拆成可独立执行的任务清单，每项写明目标、验收和负责角色：<方案摘要>" --wait --json
  ```

- **产物怎么交给下一步**：任务清单放进 `summary` 或 file 模式的 `tail`；第 3 步按清单逐项派发，每项一个 `ask`。
- **失败处理**：拆解结果不可执行 → 带着具体缺口退回第 1 步；对方长时间 working → 用 `hao status <pane>` 查看，必要时 `stop`。

## 3. 实施

- **谁来派**：`project-manager`，或调用方直接派。
- **派给谁**：`developer`、`frontend-developer`、`backend-developer`、`debugger`、`refactorer`、`test-engineer` 等 `low` 档角色；可并行多个 pane。
- **命令**：

  ```bash
  python3 scripts/hao name w2:p11 fern --role developer
  # 方式一：--wake；完成后按 wake 通知里的 hao wait 命令取结果
  python3 scripts/hao ask w2:p11 "实现任务 3：<目标与验收>；改动限定在 <路径>" --wake "$HERDR_PANE_ID"

  # 方式二（替代方式一）：不带 --wake；派发后用 hao wait 轮询
  python3 scripts/hao ask w2:p11 "实现任务 3：<目标与验收>；改动限定在 <路径>"
  python3 scripts/hao wait w2:p11 --token <shortid> --timeout 600
  ```

- **产物怎么交给下一步**：每项实现的 `summary` 加改动路径/提交号；代码量大时要求写入 file 模式的报告，直接使用返回的 `tail`（文件已删除），把内容交给初审。
- **失败处理**：超时 → `stop <pane>`（只停当前一轮）或 `abort <shortid> --interrupt`；被审批卡住 → 交用户或 `--text-only`；`low` 档角色给短 `--timeout`，见文末。

## 4. 初审

- **谁来派**：`project-manager`。
- **派给谁**：`reviewer`（代码/方案初审）、`evaluator`（质量评分）、`auditor`（安全与合规）。
- **命令**：

  ```bash
  python3 scripts/hao name w2:p12 lens --role reviewer
  python3 scripts/hao ask w2:p12 "审查 <改动范围>；只列阻塞问题与必须修改项，按严重度排序" --wait --json
  ```

- **产物怎么交给下一步**：`summary` 里的阻塞项清单；不通过则派 `debugger` 修复，修完回到第 4 步重审；通过则把结论交给第 5 步。
- **失败处理**：评审意见含糊 → 要求给出文件:行号与复现方式后重派；对方 blocked → 交用户。

## 5. 终审

- **谁来派**：调用方，或 `project-manager`。
- **派给谁**：`arbiter`（最终裁决）；也可用 `strategist` 做方向性终审。
- **命令**：

  ```bash
  python3 scripts/hao name w2:p13 moth --role arbiter
  python3 scripts/hao ask w2:p13 "只回答：通过/不通过；不通过时只列必须修改项。材料：<结论摘要与报告路径>" --wait --json
  ```

- **产物怎么交给下一步**：终审结论就是最终交付；不通过则退回第 4 步或第 3 步。
- **失败处理**：终审要求补充材料 → 收集后重派；超时或沉默 → 按文末处理，不要无限等。

## 一个完整周期的命令示例

```bash
# 1 规划
python3 scripts/hao name w2:p9 atlas --role architect
python3 scripts/hao ask w2:p9 "为登录限流写方案与验收标准" --wait --json

# 2 拆解
python3 scripts/hao name w2:p10 moss --role project-manager
python3 scripts/hao ask w2:p10 "把方案拆成任务清单：<上一步 summary>" --wait --json

# 3 实施（可并行多个 pane；下面两种取结果方式二选一）
python3 scripts/hao name w2:p11 fern --role developer
# 方式一：--wake，完成后按 wake 通知里的命令取结果
python3 scripts/hao ask w2:p11 "实现任务 1：<清单项>" --wake "$HERDR_PANE_ID"
# 方式二：不用 --wake，派发后手动等待
# python3 scripts/hao ask w2:p11 "实现任务 1：<清单项>"
# python3 scripts/hao wait w2:p11 --token <shortid> --timeout 600

# 4 初审
python3 scripts/hao name w2:p12 lens --role reviewer
python3 scripts/hao ask w2:p12 "审查任务 1 的改动；只列阻塞问题" --wait --json

# 5 终审
python3 scripts/hao name w2:p13 moth --role arbiter
python3 scripts/hao ask w2:p13 "只回答通过/不通过；材料：<初审结论>" --wait --json
```

## 对方干完活却不发完成信号

15 秒警告只覆盖「一直停在 idle/done、从未开始」的 peer。另一种情况是 peer 开始并结束了这一轮，却没有打印哨兵、也没有调用 `hao done`：此时 `ask --wait` 不会提前返回，只在 `--timeout` 到期时返回 exit 4，且 `agent_status=done`；默认超时是 30 分钟。

处理办法：

- 给 `low` 档角色显式设短超时，例如 `--timeout 300`，不要沿用默认 30 分钟。
- 收到 exit 4 且 `agent_status=done` 时，先用 `herdr pane read <pane>` 读对方 pane，确认是否已有完整答复；再决定重新派发或上报，不要盲目重试。
- 结果只走文本通道的场景优先用 `ask --text-only`，完成判定不依赖 `hao done`。

实测记录（2026-11-26）：派给 pi 的 36 次任务中有 2 次干完活但没有发完成信号，等待方一直等到超时。
