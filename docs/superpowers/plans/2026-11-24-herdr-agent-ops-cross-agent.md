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
