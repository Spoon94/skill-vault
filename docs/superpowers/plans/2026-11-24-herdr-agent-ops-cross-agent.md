# herdr-agent-ops 跨 agent 通用化方案

> 背景：本 skill 不只在 Claude Code 中使用，还要在其他 CLI agent（herdr 支持的 25 种：pi/codex/gemini/cursor/opencode/copilot…）中使用。
> 角色：Claude 审核/设计 + 跨 agent 实测；forge 实施。分支 `docs/herdr-agent-team-design`（PR #8）。

## 实证：当前代码对通用 agent 的表现（基线失败）

用一次性 pi 实例实测（pane `w2:p2E`，cwd `/private/tmp/hao-xagent`——不在本仓库、未装 skill、`hao` 不在 PATH）：

```
hao ask w2:p2E "只回答 pi-ok" --wait --timeout 180   → rc=4（超时）
pi 的原话："Let me just answer "pi-ok" and print the backup signal."
```

| # | 发现 | 证据 | 影响 |
|---|---|---|---|
| 1 | **prompt 让 peer"调用 hao done"但不带路径** | `build_prompt` 输出 `调用 hao done --token …`；此前测试能过仅因 forge 的 cwd 恰在本仓库 | 任何 cwd 不同/未装 skill/不在 PATH 的 agent 都调不了主通道，只能退回脆弱的文本哨兵 |
| 2 | **匹配器尾部装饰缺 pi 的边框字形** | 真实 pi pane 采样：内容行以 `│` 结尾，最后一块用 `┃`（U+2503）；`SENTINEL_RE` 尾部类含 `│` 无 `┃` | pi 即使正常宽度打出 `HAO_DONE hao-… ┃` 也匹配不上 |
| 3 | 装饰符集合三处各抄一份 | `SENTINEL_RE` / `_PREFIX_LINE_RE` / `_HEX_CONT_RE` 各自内联字符类 | 适配新 agent TUI 要改三处，易漏 |
| 4 | 文档 CC 专属引用 | SKILL.md `${CLAUDE_SKILL_DIR}`；README alias `~/.claude/skills/…`；protocol.md "Bash tool stdout 不进 pane snapshot" | 其他 agent 读入口文档无法解析路径 |
| 5 | 状态未知的 agent 无指引 | herdr 检测不到状态的 agent → `agent_status=unknown` → wait 默认 exit 9 | 通用 agent 首次使用即失败，不知该加 `--accept-unknown` |
| 6 | 平台限制未说明 | ledger 用 `fcntl`（POSIX） | Windows 原生不可用，文档未提 |

pi 真实渲染字形清单（采样自 wG:p1）：`│ ┃ ─ └`（边框）、`● ·`（项目符号）、`✓ ↺ █ …`（状态）。

## 修复项

### G1（P1）主通道对任何 agent 可用：prompt 内嵌 hao 的绝对调用命令
- 新增 `hao_command()`：`shutil.which("hao")` 命中 → `hao`；否则 `"<sys.executable 或 python3> "<脚本 realpath>""`（`__file__` 不可用时回退 `co_filename`，同 `_load_module` 既有模式）。
- `build_prompt` 的首选上报改为给出**完整可执行命令**：`执行：<HAO_CMD> done --token <完整令牌> --summary "<关键结论>"`；并加一句：若无法执行该命令（如跨机器），仅打印备份信号。防回显约束不变。
- **验收**：对 `/tmp` cwd 的一次性 pi 实例 `hao ask … --wait` 经台账完成并带 summary（由 Claude 实测， hostile 窄 pane 宽度下亦成立——主通道不依赖渲染）。
- 测试：prompt 含绝对路径（或 PATH 命中时为裸 `hao`）。

### G2（P1）文档去 CC 专属化
- SKILL.md：`${CLAUDE_SKILL_DIR}/scripts/hao` → 通用表述：`scripts/hao`（与本文件同目录，按加载本 skill 的路径解析；shell 中 `python3 <skill目录>/scripts/hao`），另注 PATH/alias 方式。
- README：alias 示例改为通用路径 `/path/to/herdr-agent-ops/scripts/hao`，注明各 agent 平台的 skill 目录见仓库 `INSTALL.md`。
- protocol.md："Bash tool stdout 不进 pane snapshot" → "部分 agent（如 Claude Code）的工具 stdout 不进 pane 快照"。

### G3（P1）哨兵匹配器适配其他 agent TUI
- 把装饰符收敛为**单一共享常量**（前缀类 + 尾部类），三处正则统一引用。
- 尾部/前缀类补入边框与状态字形：`┃ ┆ ┇ ┊ ┄ ┈`（竖线变体）、`─ ━`（横线）、`└ ┘`（角）、`✓ ✔`。保持 r8–r14 全部防护（standalone 锚定、<12-hex 片段、总长 ≤32、重组行强校验）不变。
- 测试夹具（正常宽度合成行，token 运行时构造）：`HAO_DONE hao-<tok> ┃`、`… │`、`│ HAO_DONE hao-<tok> │`、`● HAO_DONE hao-<tok>`、`… ┃ ✓`；并保留"提示词回现行不合并"的负例。
- protocol.md：写明装饰符集合是数据驱动的单一常量，以及如何为新 agent 采样（`herdr pane read <pane> --source recent-unwrapped`）。

### G4（P2）状态未知/无 agent 的指引
- SKILL.md 与 README：`agent_status=unknown` 的 agent 加 `--accept-unknown`；无 agent 的 pane 用 `--no-agent` 或 `file` 模式。
- 核对 exit 9 / exit 3（无 agent pane 未带 `--no-agent`）的 stderr 文案已直接提示对应 flag。

### G5（P2）平台与适用范围说明
- README 前置条件：POSIX（macOS/Linux，台账依赖 `fcntl`）、python3 ≥ 3.9、适用任何 herdr 支持的 agent（`herdr agent start --help` 列出种类）。

## 约束

1. G3 只改装饰符常量与夹具，不改合并/校验逻辑。
2. 每项带测试；全绿 + 集成冒烟；文档受 D9/D10 守卫保护。
3. 一个 conventional commit：`feat(hao): cross-agent portability (G1-G5)`，push 后简报 ≤20 行再 `hao done`。

---

# 第二轮（H1–H5）：对齐官方规范与仓库惯例

## 调研结论（仓库内 + 外部官方文档）

| 来源 | 约定 |
|---|---|
| Agent Skills 官方规范（agentskills.io/skill-creation/using-scripts） | 用**相对 skill 根目录的路径**引用脚本（`python3 scripts/x.py`），agent 自动解析；在 SKILL.md 里**列出可用脚本**；前置条件写进 SKILL.md，运行环境要求用 `compatibility` 前置字段（≤500 字符） |
| OpenCode 官方文档 | "Paths written inside the skill are relative to the directory containing `SKILL.md`" |
| Codex / Copilot CLI / pi / VS Code | 均实现 Agent Skills 规范，相对路径；pi 区分"可直接执行（shebang+可执行位）"与"需经解释器"的脚本 |
| Gemini CLI 官方文档 | 直接支持 `SKILL.md`（`~/.gemini/skills/` 或 `.gemini/skills/`）；激活后模型可访问整个 skill 目录。**不需要 `GEMINI.md`** |
| 仓库 `superpowers/writing-skills` | **经解释器调用脚本，绝不裸跑**——某些 harness 打包器会抹掉可执行位 |
| 仓库 `diagram/diagram-image` | `SKILL_ROOT="${CLAUDE_SKILL_DIR:-<Codex skill 元数据里的绝对路径>}"; python3 "$SKILL_ROOT/scripts/…"`；"不要假设 cwd 或上一条命令的 shell 变量还在" |
| 仓库 INSTALL.md | 各平台 skill 目录表；但 Gemini 行写"参考 `GEMINI.md`"——仓库 0 个 skill 有该文件，属过时约定 |

**结论**：当前 SKILL.md 的 `python3 <skill目录>/scripts/hao` 方向对，但缺三样——规范要求的"可用脚本"清单、per-harness 的路径解析说明（`SKILL_ROOT` 惯用法）、经解释器调用的明确约束；frontmatter 缺 `license`/`compatibility`。此外 peer 侧仍依赖长绝对路径命令——装到 PATH 是对任何 agent 都最短最稳的形态。

## 修复项

### H1（P1）SKILL.md 对齐官方规范与仓库惯例
- 调用形式统一为 `python3 scripts/hao …`（相对 SKILL.md 所在目录）。
- 加「定位脚本」小节（借 diagram-image 写法）：各平台按 SKILL.md 所在目录解析；Claude Code 为 `${CLAUDE_SKILL_DIR}`；shell 的 cwd 不在 skill 目录时用一行 `SKILL_ROOT="${CLAUDE_SKILL_DIR:-<本 SKILL.md 所在目录>}"; python3 "$SKILL_ROOT/scripts/hao" …`；写明不要假设 cwd 或上一条 shell 变量还在。
- 加「可用脚本」清单：`scripts/hao`。
- 前置条件写进正文：herdr ≥ 0.9.5、`HERDR_ENV=1`、python3 ≥ 3.9、POSIX。
- 明确"一律经解释器调用，不裸跑"；alias/包装器同样经 `python3`。
- frontmatter 加 `license: MIT` 与 `compatibility: "Requires herdr >= 0.9.5 with HERDR_ENV=1, python3 >= 3.9, POSIX (macOS/Linux)."`。

### H2（P1）`hao install`：一条命令装到 PATH
- `hao install [--dir DIR]`：在 DIR（默认 `~/.local/bin`）写入包装器 `hao`：`#!/bin/sh` + 标记注释 `# hao wrapper: herdr-agent-ops` + `exec "<python>" "<abs hao>" "$@"`（不依赖脚本可执行位）。幂等；DIR 不在 PATH 时输出 `export PATH` 提示。`--print-alias` 只打印不写文件；`hao uninstall`。
- `hao_command()`：PATH 上的 `hao` 仅当文件内容含 wrapper 标记（或即本脚本）才信任，否则回退绝对路径（防同名程序）。
- `doctor` 增加 `hao on PATH` 检查，未装则提示 `hao install`。
- 测试：临时目录安装→包装器可用；幂等；陌生同名 `hao` 不被信任；`--print-alias`。

### H3（P2）README
- 30 秒上手第 0 步改为 `python3 <skill目录>/scripts/hao install`，alias 作为备选；命令面表加 `install`/`uninstall`；一句话写明相对路径约定并指向 INSTALL.md。

### H4（P2）peer prompt
- 已装 → `hao done …`；未装 → 绝对路径。两种形态均经解释器。

### H5（P3）INSTALL.md Gemini 行修正
- 改为：`~/.gemini/skills/` 或项目内 `.gemini/skills/`（官方支持 `SKILL.md`）。只改这一行。

## 验收（Claude）
- SKILL.md：无仅限 `${CLAUDE_SKILL_DIR}` 的调用形式；含相对路径形式、定位说明、可用脚本清单、前置条件。
- `hao install --dir <临时目录>` → 包装器可执行且 `hao doctor` 正常；`hao_command()` 随之输出裸 `hao`。
- 跨 agent 复测：以临时 PATH 目录起一次性 pi，prompt 应为短命令 `hao done …`，任务经台账完成。
