# herdr-agent-ops 设计稿 v2

> 状态：待 forge 复审 → 用户授权 · 日期：2026-11-22 · 分支：docs/herdr-agent-team-design
> v2 变更：改名 herdr-agent-team→herdr-agent-ops（CLI hat→hao，label 前缀 hat-→hao-）；修复 forge 审核 16 条问题；新增功能/性能/容灾/扩展性/易用性五维优化；纳入编排者实测发现。

## 1. 背景与痛点

herdr 多 agent 协作三痛点：
1. **任务级等待缺失**：`herdr agent wait`/`agent prompt --wait` 只看生命周期（idle/done/blocked），不是任务完成信号；跨机器更难。
2. **名字不持久**：agent name 在 agent 退出/被替换时清除；重启窗口内 live name 丢失，label 才是稳定句柄。
3. **取名难**：要短、有意义、贴合分工。

## 2. 命名与调用

- skill 名：`herdr-agent-ops`；CLI：`hao`（herdr agent ops）；受管 pane label 前缀：`hao-`。
- 调用路径（SKILL.md 必须写明）：Claude Code 用 `${CLAUDE_SKILL_DIR}/scripts/hao`；或安装到 PATH 后直接 `hao`。远端无 python3/hao 时退化为“agent 手动打印哨兵”。
- `hao doctor` 检查：python3≥3.9、herdr 版本、`HERDR_ENV=1`、machine profile、`resume_agents_on_restore` 配置。
- 所有命令支持 `--json`（供 agent 解析）与人读默认输出。

## 3. 已确认决定

| 维度 | 决定 |
|---|---|
| 跨机器 | 封装 `herdr --machine <label>`；**本机实测 machine list=[]，跨机器仅 stub 验证，spec 明确标注未端到端验证** |
| 持久化载体 | 零注册表：`hao-` 前缀 pane label 是我们控制的、与 agent 生命周期解耦的角色槽位；herdr 自身 agent_name/resume 是 best-effort，不作契约 |
| 持久化范围 | server/客户端重启 + agent 退出重开 + unsupported kind + resume 失败 |
| 命名 | 优雅代号，`^[a-z]{4,6}$`，**per-machine 唯一**（herdr live name 按 server 唯一，跨机器可同名）|
| name vs label | agent name=裸代号；label=`hao-<代号>[-<scope>]`；**scope 仅标签注解，不参与 agent name** |
| 冲突模型 | 一代号一 agent；同 role 多 pane 必须用不同代号 |
| 等待 | 哨兵 token（拆分防回显）+ 行首锚定正则 + 基线比对；blocked/exited 立即返回 |
| 恢复时机 | 仅 skill 入口 `hao restore`；可选 SessionStart hook（扩展项）|
| 词表 | 40 组×40=1600，全部 `^[a-z]{4,6}$`、全局唯一、无保留字、无灰色词 |

## 4. 目录结构

```
herdr-agent-ops/
├── SKILL.md
├── scripts/hao              # Python3 单文件，stdlib only
├── references/
│   ├── names.md             # 1600 名 + 含义 + 分组 + 中英文关键词别名
│   ├── names.local.md       # 可选：用户自定义组/名（扩展，不改 vendored 池）
│   ├── protocol.md          # 哨兵协议/跨机器/错误映射
│   └── restore.md           # label 解析 + pre-flight 算法
└── tests/
    ├── test_hao.py          # 单元 + herdr stub 错误拼装
    ├── test_names.py        # 词表完整性 + 保留字 + 敏感词脚本化检查
    └── integration/         # named test session 真实集成测试
```

## 5. Target 解析（forge #9 + 实测）

`hao` 的 `<target>` 语法，先解析到**唯一 pane**：
- `hao-...` → 按 label 查（支持 `hao-<role>-<scope>` 与裸 `hao-<role>`）
- `w<N>:p<M>` → pane id；**兼容 `w<N>:t<K>:p<M>`，归一化为 `w<N>:p<M>`**（实测用户写 w2:t1:p9，真实 id 是 w2:p9）
- 其他 → live agent name
- 零匹配→exit 3；多匹配→exit 6（歧义），需 `--pick <pane>`
- 解析在目标机器上做（`--machine` 时用远端 list）
- `hao ask` 打印的下一步命令用**稳定 target（label 或 pane id）**，不用会变的 agent name
- 实测：`herdr agent get <label>` 返回 agent_not_found——label 不是 herdr agent target，必须由 hao 先解析成 pane id 再调 herdr

## 6. 命名模型（forge #2/#3/#16）

- agent name：`^[a-z]{4,6}$`，per-machine live 唯一。
- label：`^hao-([a-z]{4,6})(?:-([a-z0-9][a-z0-9-]{0,11}))?$`；scope 仅小写字母/数字/连字符，1–12 字符（**修正：不含 . _，长度上限 12 而非 13**）；label 总长≤23。
- **一代号一 agent**：scope 只进 label，不进 agent name。`hao name` 预检所有 live agent names + 所有 label 解析出的 role + stale label 占位；冲突 exit 6。同 role 多 pane 必须换不同代号（如 hawk/lynx）。
- `hao name <target> <name> [--scope S]`：两个位置参数。target 为 shell-only pane 时只设 label（允许）；target 已有非 hao- label 时需 `--force`。**原子性：先设 label 再改 agent name；agent rename 失败则保留 label 交给 restore**。
- `hao clear <target>`：先清 agent name 再清 hao- label；**不动非 hao- label**（除非 --force）。
- 示例统一用合法代号：`hao name w2:p9 hawk --scope api` → agent `hawk` + label `hao-hawk-api`。

## 7. 持久化与 restore（forge #4/#5/#10）

**口径修正**：session.json 同时存 label 和 agent_name；config `[session] resume_agents_on_restore=true` 会在 server restart 后恢复受支持 agent（如 Claude）的会话。所以“重启必丢名”不准确。label 是我们控制的解耦槽位；herdr 的 agent_name/resume 是 best-effort。真正需要 label 兜底：agent 退出/被替换、unsupported kind、resume=false、resume 失败。

restore 算法：
1. **默认只扫当前 `HERDR_WORKSPACE_ID`**；`--workspace W`/`--all` 才扩大。绝不默认全局（本机 8 个 workspace，防误伤）。
2. **pre-flight plan**：枚举范围内 hao- label→解析 role/scope→映射 pane→当前 agent；检测 role 冲突、live name 已被占、startup pending、stale label（无 agent）、非法 label。
3. **不自动选 winner**：歧义报 exit 6 + 候选列表，要求 `--pick <pane>` 或换代号/scope。workspace/tab/pane 自然序仅用于展示，不决定身份（pane_id 是 opaque，字符串排序 w2:p10<w2:p9 不可靠）。
4. 只对无歧义匹配 apply；**不覆盖已有非空 agent name**（只填无名或已匹配者），降低 repurpose 劫持。shell-only pane 跳过。
5. **幂等 + 部分失败报告**：列出成功/失败/跳过，不留静默半恢复态。
6. `--dry-run` 打印 plan；变更前输出 machine/workspace/tab/pane/cwd/agent。
7. 处理 “agent name cannot change while startup pending”：等待/重试/报告。
8. `hao doctor` 列 stale/invalid/重复 label，读 resume 配置并提示；文档写明 repurpose pane 前先 `hao clear`。
9. 真实 server restart 测试在**隔离 named session**做，不停默认 server。

## 8. 派活与等待协议（forge #1/#6/#13 + 实测）

**哨兵防回显（P0，forge 已复现）**：prompt 里不出现完整哨兵。token=`hao-<12–16hex>`；prompt 把 token 拆两段展示，指令要求 agent 拼接后把 `HAO_DONE <token>` 作为**最后一行**打印。`hao ask` 构造完 prompt 后扫描，若含完整哨兵则拒绝/改写。

`hao wait`：
- `--source recent-unwrapped`；用 `--regex '^HAO_DONE <token>\s*$'` 行首锚定；**ask 时捕获输出基线，只认基线之后新出现、且位于快照尾部 N 行内的命中**（杜绝 prompt 回显/预置哨兵假命中）。
- **并行轮询 `agent get`**：blocked→立即 exit 5 + 状态 + 尾部；exited/pane closed→exit 3；绝不自动点审批。
- 超时→exit 4 + `agent get` 状态 + 尾部输出。**默认超时放宽（如 30m）且可 `--timeout 0` 无限/更大**（实测 forge 深度审核 14m52s，旧 10m 默认扛不住）。token 稳定，可重复 wait 不必重发。
- **进度可见**：`--progress` 周期打印 agent 状态 + 最后一行心跳；`hao status <target>` 随时查。
- **一个 pane 同时只有一个 outstanding task**：`hao ask` 要求 target idle，否则 exit 6，除非 `--queue`。防并发交错。
- `hao ask` 即使发送失败也返回/打印 token；**不自动重试**（herdr：连接失败≠未送达）。
- `hao done --token T [--summary]`：先打 summary 再打哨兵（最后一行）；须在 agent 自己 pane 里运行才会被 wait-output 看到；远端无 hao 时按 prompt 手动打印。
- 文档写明：**哨兵是协作信号，不是安全边界**。
- 大输出回退：请 agent 把结果写成 Markdown 文件、只回路径，`hao result` 读取（herdr 文档推荐的 fallback）。

## 9. 错误码映射（forge #7）

hao 退出码：0 成功 / 2 用法 / 3 target 不存在·exited·pane closed / 4 超时 / 5 blocked / 6 冲突·歧义·name taken / 7 machine·profile 不可用 / 8 herdr·server 错误。

必须解析 herdr 的 JSON `error.code`/stderr，**不透传 herdr 退出码**。映射表：

| herdr | hao |
|---|---|
| agent_name_taken / agent_target_ambiguous | 6 |
| pane_not_found / agent_not_found | 3 |
| timeout（wait-output）| 4 |
| agent_blocked | 5 |
| unknown machine / no profile | 7 |
| agent_prompt_stalled / remote connection failure / 其他 server error | 8 |

mutating 命令（ask/name/clear/restore）**不盲目重试**；区分“没发出/可能已发出”。

## 10. 跨机器（forge #8）

- 本机 `machine list --json=[]`，跨机器**未端到端验证**，仅 stub；spec/doctor 明确标注。
- `--machine` 不能与 `--session`/`--remote` 组合；hao 不把 `--current`/本地 ID 传给 `--machine`。
- name/clear/suggest/list/restore/ask/wait 均支持 `--machine`；target 解析在远端。
- `hao doctor --machine M` 用 `machine status M --json` 查 enabled/reachable/version；`machine list --json` 只查存在性；无/未知 profile→exit 7。
- 远端 server 须已运行且 API 兼容；forwarding 不启动 server；连接失败≠mutation 未发生。

## 11. suggest（forge #11）

- names.md 每组写**中英文关键词别名** + 确定性打分；任务文本→组。
- “未占用”=所有 live agent names + 所有 label 解析 role + stale label 占位（per-machine）。
- **排除保留字**（hao 子命令 + herdr 命令/状态 + 领域词，见 §14）；组耗尽→相邻组 fallback 或 `--custom`。
- `hao suggest --json` 输出候选/组/理由；验收用 3–5 个中英文 task。

## 12. 五维优化

### 功能
- 核心：name/restore/ask/wait/done/list/suggest/clear/doctor。
- 新增：`hao status`（进度）、`hao say`（fire-and-forget 无哨兵）、`hao broadcast`（多 target）、`hao result`（读结果文件）、`hao export/import`（label 快照备份/恢复，容灾用，非 live 注册表）。
- target 归一化（w:t:p→w:p）、`--json`、稳定 target 回显。
### 性能
- 等待用 server 侧 `pane wait-output`，非忙轮询；回退轮询间隔可调。
- `--lines` 限界，避免读全量 scrollback；restore 单遍 pre-flight；suggest 按组索引；批量 rename。
### 容灾
- 哨兵防回显 + 基线比对；blocked/exited/closed 立即返回；超时给状态+尾部。
- mutating 不盲重试；一 pane 一 outstanding task；restore 幂等 + 部分失败报告。
- `hao export/import` 手动快照应对 label 丢失；doctor 检 stale/invalid/dup + resume 配置；远端连接失败先查远端态再决定。
### 扩展性
- `names.local.md` 自定义组/名（不改 vendored 池）；`--custom`；保留字过滤可配置。
- 等待后端可插拔（哨兵默认 / 文件结果 / 纯生命周期）；多 machine；可选 SessionStart hook；agent-kind 无关。
### 易用性
- `hao` 无参=帮助+当前 roster 仪表盘；`hao name` 省略 name 时交互式 suggest。
- 短别名（n/r/a/w/d/l/s）；错误带下一步提示；mutating 全支持 `--dry-run`；doctor 给可执行修复建议。

## 13. 安全性

- 不碰 `herdr server stop`、不主动关 pane；只改 hao- label 与显式 target 的 agent name。
- restore 默认当前 workspace；非 hao- label 需 --force；不覆盖已有 agent name。
- 跨机器先校验 profile；不猜 SSH host；不自动点审批。

## 14. 敏感审查（forge #15，脚本化可复现）

政策落成 deny/allow 规则 + `tests/test_names.py` 脚本化检查，不再只写“已审查”。
- **deny**：政治/宗教/暴力/伤害/身体/族群/性/毒品/金融/PII/凭证，以及 **hao/herdr 保留字**。
- **保留字 deny 集**：wait done list read test agent name ask clear doctor suggest status export import restore pane idle working blocked unknown hat hao herdr task token scope label role machine session tab workspace terminal send prompt focus split close。
- **灰色词处理（round-2，40 个）**：宗教 corona/coven/chapel/censer/bless/karma、暴力 combat/bruise、身体 diet、语言/族群 greek/roman/latin/kanji/hanzi/pinyin/hangul/kana/hira（与已替换的 thai/hindi/maori 标准对齐，全部替换）、保留字 agent/clear/doctor/done/export/idle/import/label/list/pane/read/role/scope/status/task/test/wait/send/prompt/focus/split/close。
- 数据完整性：40 组×40、1600 唯一、全 `^[a-z]{4,6}$`、无保留字、无灰色词（脚本断言）。

## 15. 验收（forge #12，可测）

单元（stub）+ 集成（named test session，真实 split/set label/start agent/restore/ask/wait，含 echo 反例；server restart 用隔离 session）。修正示例：
1. `hao name w2:p9 hawk --scope api` → agent hawk + label hao-hawk-api
2. agent 退出后 `herdr agent start <NAME>`（NAME 必填）重开 → restore 从 label 恢复 hawk
3. label=yaml 的 pane 不被 restore 触碰
4. 两 pane 都标 hao-hawk → 第一个恢复 hawk，第二个 exit 6，不产生 hawk2
5. 两 pane hao-hawk-api / hao-hawk-web → 因 agent name hawk 冲突 exit 6（一代号一 agent）
6. ask/wait：预置哨兵或 prompt 回显时 wait **不得**成功；仅任务完成后新打印的哨兵才算
7. machine：fixture 覆盖 machine list 两种 shape、unknown profile、remote down、machine+session 组合；本机无 profile 标注未验证
8. suggest：3–5 中英文 task；“live 重名”=扫 agent names + all labels + stale labels
9. test_names.py：完整性 + 保留字 + 敏感词断言

## 16. 名字词表（40 组×40，round-2 后）

| # | 分工 | 主题 | 40 个候选 |
|---|---|---|---|
| 1 | 规划编排 | 地图/方向/星光/秩序 | `atlas` `north` `lumen` `vega` `orion` `polar` `lyra` `aegis` `ethos` `prime` `alba` `alto` `amber` `axis` `order` `logic` `arch` `amble` `nova` `aurora` `vision` `intent` `arbor` `ardor` `vista` `rudder` `tack` `spire` `apex` `summit` `zenith` `peak` `crest` `cycle` `phase` `stage` `step` `scheme` `tactic` `method` |
| 2 | 需求产品 | 价值/用户/市场/目标 | `value` `worth` `lily` `brief` `pitch` `angle` `lotus` `demand` `offer` `solve` `case` `aria` `listen` `market` `growth` `trend` `goal` `core` `first` `seed` `need` `want` `wish` `must` `armor` `aroma` `aspen` `survey` `niche` `epic` `maple` `ticket` `beta` `pilot` `launch` `deck` `deal` `query` `agile` `sprint` |
| 3 | 用户研究 | 观察/倾听/行为/群体 | `study` `learn` `sense` `feel` `mood` `quote` `heat` `funnel` `drop` `churn` `retain` `habit` `aura` `cohort` `panel` `poll` `group` `circle` `avian` `azure` `field` `shadow` `notice` `meadow` `talk` `chat` `reply` `depth` `broad` `narrow` `babel` `bail` `spot` `bale` `bark` `barn` `baron` `basil` `basin` `mind` |
| 4 | 架构接口 | 结构/边界/契约/骨架 | `frame` `shell` `layer` `bayou` `proto` `module` `plugin` `spine` `base` `form` `shape` `span` `dome` `vault` `keel` `mast` `pillar` `column` `scale` `plane` `beam` `girder` `joist` `rafter` `lintel` `corbel` `plinth` `atrium` `facade` `link` `schema` `driver` `model` `object` `entity` `bean` `tree` `heap` `myrtle` `trie` |
| 5 | 设计体验 | 色彩/形态/笔触/韵律 | `muse` `iris` `opal` `forma` `motif` `verve` `poise` `glint` `bloom` `tint` `tone` `shade` `brush` `easel` `craft` `sculpt` `chisel` `etude` `lyric` `sonnet` `draft` `wire` `layout` `space` `align` `margin` `border` `radius` `ombre` `glow` `matte` `glass` `frost` `noise` `grain` `stripe` `color` `chroma` `swatch` `icon` |
| 6 | 视觉品牌 | 标识/排版/质感/风格 | `brand` `logo` `mark` `emblem` `badge` `sigil` `banner` `poster` `flyer` `cover` `spread` `type` `serif` `sans` `font` `weight` `italic` `bold` `light` `heavy` `gothic` `rhythm` `photo` `crop` `blur` `sharp` `beard` `filter` `gloss` `satin` `linen` `paper` `paint` `stroke` `beast` `deco` `retro` `modern` `clean` `subtle` |
| 7 | 前端体验 | 交互/动效/组件/界面 | `cursor` `click` `touch` `swipe` `motion` `anim` `ease` `flow` `fluid` `smooth` `crisp` `nettle` `glide` `slide` `shift` `hover` `canvas` `sketch` `menu` `theme` `render` `reflow` `bundle` `chunk` `beech` `fetch` `state` `store` `props` `hook` `input` `toggle` `slider` `picker` `modal` `toast` `card` `drawer` `sheet` `dialog` |
| 8 | 后端服务 | 服务/队列/协议/并发 | `serve` `route` `queue` `beetle` `cron` `beige` `socket` `stream` `buffer` `pipe` `broker` `router` `server` `engine` `retry` `batch` `async` `event` `shard` `raft` `topic` `pubsub` `fanout` `rest` `grpc` `soap` `http` `cookie` `header` `body` `orchid` `code` `view` `join` `berry` `offset` `commit` `bevel` `lease` `atomic` |
| 9 | 移动桌面 | 触控/设备/离线/同步 | `mobile` `birch` `hybrid` `tablet` `bison` `wear` `haptic` `vibe` `shake` `tilt` `rotate` `orient` `screen` `palm` `tray` `widget` `hotkey` `pull` `stash` `online` `sync` `local` `remote` `push` `notify` `power` `drain` `sleep` `wake` `resume` `pause` `play` `retina` `inset` `notch` `keypad` `share` `petal` `blade` `start` |
| 10 | 实现构建 | 锻造/金属/结构/火 | `forge` `flint` `ember` `anvil` `cedar` `kiln` `steel` `iron` `bolt` `gear` `lever` `pylon` `truss` `brick` `mortar` `weld` `solder` `alloy` `smelt` `hearth` `cast` `mold` `mint` `carve` `lathe` `mill` `blaze` `clamp` `vise` `file` `rasp` `bleak` `wrench` `pliers` `ruler` `tape` `glue` `epoxy` `resin` `clay` |
| 11 | 数据工程 | 管道/存储/格式/血缘 | `ingest` `dedupe` `enrich` `merge` `pine` `arrow` `avro` `json` `yaml` `lake` `pond` `mart` `cube` `fact` `star` `snow` `origin` `source` `target` `sink` `spigot` `faucet` `valve` `null` `blank` `empty` `dupe` `stale` `fresh` `late` `drift` `skew` `sched` `poplar` `backup` `save` `loader` `parser` `mapper` `sorter` |
| 12 | 数据科学 | 统计/推断/图表/概率 | `stats` `blimp` `median` `range` `quart` `season` `factor` `latent` `poppy` `train` `score` `rank` `topk` `report` `infer` `causal` `effect` `impact` `lift` `uplift` `pivot` `slice` `dice` `rollup` `plot` `legend` `tick` `bins` `blitz` `bluff` `prior` `bayes` `markov` `blurb` `blush` `random` `resid` `ridge` `lasso` `gini` |
| 13 | 机器学习 | 模型/训练/推理/神经 | `neuron` `neural` `boat` `epoch` `embed` `reed` `window` `rose` `reward` `action` `head` `norm` `relu` `tanh` `gelu` `lstm` `unet` `lora` `qlora` `peft` `rlhf` `search` `grad` `bobbin` `warmup` `prune` `sparse` `dense` `tune` `steer` `logit` `spike` `micro` `macro` `fold` `expert` `small` `large` `tiny` `giant` |
| 14 | 测试实验 | 试验/基准/模糊/金丝雀 | `trial` `sample` `bench` `bough` `assert` `expect` `bourn` `stub` `suite` `golden` `bower` `canary` `chaos` `stress` `load` `surge` `burst` `quota` `metric` `grade` `shrub` `verify` `plan` `setup` `before` `after` `unit` `brace` `brass` `brave` `happy` `corner` `flaky` `line` `branch` `soak` `perf` `blue` `green` `check` |
| 15 | 调试修复 | 追踪/探针/疗愈/修补 | `hound` `trace` `probe` `spark` `rivet` `mend` `heal` `cure` `balm` `salve` `suture` `splint` `remedy` `tinker` `patch` `clue` `trail` `track` `brawn` `ferret` `bisect` `repro` `bread` `breeze` `brew` `warn` `root` `cause` `reason` `hotfix` `reduce` `shrink` `attach` `briar` `brim` `brine` `brisk` `brook` `loop` `broom` |
| 16 | 验证审阅 | 锐眼/量具/证明/守卫 | `hawk` `lens` `prism` `ward` `proof` `verity` `broth` `edge` `sift` `trust` `gauge` `plumb` `level` `square` `assay` `valid` `scan` `sweep` `shield` `lynx` `glance` `peer` `skim` `sprig` `bubble` `spec` `canon` `stamp` `pass` `buckle` `veto` `assent` `ruling` `appeal` `patrol` `scout` `ranger` `vigil` `look` `rule` |
| 17 | 安全隐私 | 锁/密钥/防护/威胁 | `guard` `lock` `crypt` `buff` `bulb` `permit` `policy` `safe` `secure` `seal` `sign` `auth` `login` `access` `grant` `deny` `threat` `bumper` `sentry` `moat` `hash` `salt` `nonce` `hmac` `vuln` `bunch` `burl` `bush` `bustle` `butte` `button` `cabin` `zero` `least` `purple` `cactus` `cadet` `cage` `cairn` `cake` |
| 18 | 基础设施 | 云/网络/存储/平台 | `cloud` `infra` `deploy` `subnet` `switch` `tunnel` `egress` `packet` `swarm` `hive` `host` `image` `volume` `disk` `mount` `blob` `bucket` `pool` `mirror` `memory` `hyper` `calf` `metal` `chip` `board` `fabric` `vlan` `vxlan` `dhcp` `ipam` `cidr` `ospf` `mpls` `callus` `resize` `init` `config` `param` `cert` `jump` |
| 19 | 发布运维 | 信标/港湾/航行/信号 | `beacon` `harbor` `anchor` `helm` `pulse` `signal` `watch` `port` `dock` `gate` `tower` `keep` `ferry` `orbit` `comet` `cameo` `radar` `sonar` `buoy` `canal` `ship` `revert` `swap` `bump` `repo` `binary` `dist` `prod` `sanity` `undo` `redo` `freeze` `thaw` `flag` `health` `vendor` `roll` `stable` `latest` `pinned` |
| 20 | 监控成本 | 告警/预算/计量/节俭 | `candle` `canoe` `canopy` `canyon` `cape` `limit` `rate` `util` `usage` `caper` `carol` `cask` `castle` `cater` `stat` `tally` `count` `spruce` `thrift` `frugal` `dash` `uptime` `floor` `cavern` `ceil` `cellar` `cement` `thorn` `chafe` `chaff` `spare` `oncall` `pager` `chair` `rota` `quiet` `silent` `chalk` `chant` `twig` |
| 21 | 网络通信 | 协议/信号/传输/连接 | `https` `smtp` `imap` `sftp` `mqtt` `amqp` `coap` `quic` `radio` `wave` `fiber` `coax` `cable` `ping` `pong` `call` `dial` `ring` `beep` `buzz` `feed` `cell` `slot` `band` `modem` `codec` `demux` `parley` `chirp` `squawk` `shout` `speak` `flare` `uplink` `roam` `tether` `pair` `bond` `hail` `blink` |
| 22 | 存储检索 | 索引/结构/容器/查找 | `folder` `seek` `find` `lookup` `match` `sort` `btree` `mvcc` `chase` `crdt` `paxos` `chasm` `mmap` `cold` `warm` `tier` `hnsw` `chaste` `radix` `octree` `extent` `inode` `dentry` `vacuum` `parse` `format` `cheek` `fifo` `lifo` `pack` `shelf` `rack` `locker` `chest` `crate` `pallet` `carton` `desk` `closet` `spool` |
| 23 | 研究检索 | 智慧/索引/解密/探索 | `sage` `index` `cipher` `quest` `raven` `wren` `lark` `finch` `heron` `swift` `robin` `magpie` `merlin` `cheese` `rune` `lore` `riddle` `enigma` `lexis` `path` `browse` `chef` `delve` `scent` `eagle` `falcon` `osprey` `condor` `kite` `stork` `ibis` `egret` `swan` `goose` `teal` `cherry` `gull` `tern` `puffin` `petrel` |
| 24 | 文档表达 | 书写/诗行/故事/清晰 | `quill` `verse` `fable` `glyph` `tome` `prose` `story` `voice` `echo` `page` `leaf` `scroll` `rhyme` `stanza` `meter` `chess` `phrase` `syntax` `lucid` `memo` `write` `edit` `copy` `paste` `clip` `note` `digest` `title` `style` `term` `jargon` `slang` `cite` `claim` `essay` `blog` `post` `book` `issue` `figure` |
| 25 | 本地化翻译 | 语言/文字/区域/文化 | `locale` `lingua` `verb` `noun` `script` `violet` `willow` `yarrow` `badger` `beagle` `beaver` `choir` `chorus` `chrome` `text` `word` `clause` `idiom` `tongue` `globe` `global` `region` `zone` `area` `custom` `chuck` `chum` `char` `ascii` `boar` `bobcat` `camel` `cider` `cigar` `cinder` `cinema` `circus` `citrus` `city` `clam` |
| 26 | 合规治理 | 议事/契约/裁决/秩序 | `nexus` `envoy` `herald` `relay` `clang` `bridge` `warden` `keeper` `forum` `agora` `quorum` `proxy` `accord` `truce` `pact` `clap` `civic` `polis` `realm` `clash` `ethic` `moral` `clasp` `claw` `cleat` `cleft` `clever` `cliff` `cattle` `house` `cling` `cloak` `clod` `clog` `peace` `cloth` `clover` `honor` `equity` `fair` |
| 27 | 法务风控 | 法律/合同/风险/保险 | `clown` `clump` `terms` `breach` `waiver` `patent` `docket` `hedge` `damage` `clutch` `coast` `coat` `cobalt` `cougar` `coyote` `will` `estate` `heir` `settle` `defend` `accuse` `plead` `cobble` `alibi` `motive` `notary` `clerk` `scribe` `assure` `insure` `surety` `cobra` `cocoa` `coil` `liable` `caveat` `umpire` `deed` `lien` `escrow` |
| 28 | 教学讲解 | 导师/课程/练习/启发 | `tutor` `mentor` `coach` `guide` `lesson` `course` `class` `quiz` `exam` `hint` `demo` `show` `tell` `wonder` `answer` `simple` `plain` `skill` `repeat` `recall` `teach` `myth` `tale` `saga` `school` `campus` `studio` `ponder` `think` `recap` `flash` `praise` `tweak` `easy` `hard` `vivid` `cola` `novice` `collar` `mentee` |
| 29 | 支持成功 | 帮助/关怀/响应/忠诚 | `help` `care` `assist` `rescue` `smile` `kind` `nice` `calm` `soothe` `triage` `assign` `refer` `loyal` `greet` `colon` `colt` `comb` `thread` `video` `glad` `cheer` `sorry` `dragon` `comic` `comma` `conch` `cone` `manual` `howto` `please` `update` `inform` `advise` `portal` `center` `heart` `hope` `confer` `hand` `conga` |
| 30 | 销售市场 | 交易/推广/渠道/激励 | `sell` `sale` `duck` `lead` `promo` `social` `viral` `hype` `news` `press` `asset` `media` `free` `resell` `distro` `reach` `coupon` `upsell` `cart` `basket` `shop` `retail` `bazaar` `mall` `booth` `stand` `engage` `tend` `site` `maker` `champ` `bounty` `bonus` `gift` `prize` `award` `medal` `points` `outlet` `kiosk` |
| 31 | 内容社交 | 媒体/社区/互动/创作 | `vlog` `reel` `short` `live` `like` `follow` `handle` `emoji` `upvote` `fawn` `club` `guild` `team` `crew` `squad` `cook` `cool` `scene` `beat` `tempo` `chord` `melody` `song` `audio` `zine` `onair` `meet` `meetup` `camp` `gather` `cope` `game` `arcade` `puzzle` `trivia` `kudos` `tile` `flair` `about` `mosaic` |
| 32 | 财务计费 | 货币/账务/薪酬/投资 | `copper` `cord` `cork` `corn` `cornet` `fish` `corpus` `corral` `corset` `entry` `annual` `month` `week` `paid` `gross` `cortex` `cosmic` `cosmos` `cotton` `couch` `county` `couple` `cousin` `cove` `flea` `covet` `cozy` `crab` `crack` `cradle` `cram` `crank` `crater` `crave` `crayon` `craze` `cream` `create` `creek` `creep` |
| 33 | 人力招聘 | 人才/职业/团队/流动 | `talent` `hire` `staff` `career` `ladder` `frog` `review` `rubric` `folio` `buddy` `morale` `perk` `values` `office` `seat` `room` `apply` `intern` `junior` `senior` `crib` `cringe` `ally` `croak` `crock` `crocus` `crook` `leave` `break` `repose` `roster` `swing` `flex` `temp` `perm` `cross` `crouch` `nest` `roost` `burrow` |
| 34 | 项目管理 | 进度/看板/节奏/交付 | `scrum` `wrap` `gantt` `todo` `gecko` `doing` `crow` `time` `date` `work` `urgent` `major` `minor` `point` `size` `agenda` `item` `lane` `swim` `slack` `float` `fast` `slow` `speed` `pace` `weekly` `daily` `clock` `timer` `bell` `remind` `next` `last` `kick` `begin` `open` `ready` `park` `hold` `hare` |
| 35 | 采购供应链 | 物流/仓储/运输/交易 | `supply` `tender` `cargo` `depot` `yard` `quay` `berth` `crane` `fork` `hoist` `chute` `belt` `roller` `seller` `crude` `trader` `cruise` `haggle` `bulk` `sack` `tote` `skid` `truck` `rail` `crumb` `safety` `pick` `haul` `unload` `crunch` `robot` `convey` `lading` `tanker` `barge` `vessel` `crush` `drum` `pier` `wharf` |
| 36 | 生态合作 | 连接/共生/联盟/共享 | `place` `crust` `addon` `biome` `mutual` `coop` `cuddle` `cuff` `invest` `spoke` `axle` `door` `give` `trade` `barter` `lend` `borrow` `cumin` `cupola` `grove` `forest` `reef` `coral` `kelp` `moss` `fern` `vine` `shoal` `curd` `knot` `weave` `braid` `strand` `curfew` `shared` `common` `cohost` `clone` `curate` `merit` |
| 37 | 战略分析 | 框架/决策/竞争/格局 | `swot` `pest` `porter` `five` `curl` `chain` `life` `choice` `thesis` `assume` `lean` `wedge` `ocean` `weak` `assess` `turn` `move` `stake` `return` `yield` `bull` `bear` `lion` `tiger` `shark` `curry` `beach` `stance` `codex` `firm` `curt` `land` `cute` `wolf` `orca` `arena` `turf` `sector` `domain` `basis` |
| 38 | 创意灵感 | 想象/新奇/玩心/火花 | `idea` `dream` `cymbal` `whim` `fancy` `novel` `unique` `rare` `weird` `wild` `dare` `draw` `doodle` `mash` `blend` `remix` `twist` `flip` `bend` `fairy` `genie` `magic` `spell` `charm` `joke` `quip` `jest` `jolly` `merry` `zest` `bang` `boom` `fizz` `zing` `neon` `improv` `adlib` `riff` `solo` `encore` |
| 39 | 伦理安全 | 伤害/美德/诚实/守护 | `cynic` `acorn` `alder` `misuse` `aloe` `harden` `virtue` `aster` `good` `bamboo` `truth` `honest` `candor` `opaque` `curb` `brake` `right` `wisdom` `aware` `attune` `heed` `just` `equal` `same` `candid` `frank` `cred` `brier` `dahlia` `gentle` `still` `meek` `humble` `modest` `daisy` `blame` `shame` `regard` `esteem` `ebony` |
| 40 | 领域专家 | 医学/科学/工程/艺术 | `medic` `vital` `juris` `earth` `chem` `astro` `math` `clinic` `pharma` `elder` `flora` `neuro` `cardio` `derma` `onco` `renal` `immune` `garden` `hazel` `heath` `holly` `laurel` `nurse` `hippo` `econ` `devops` `lilac` `mecha` `aero` `auto` `civil` `struct` `mechan` `elect` `optic` `editor` `music` `visual` `film` `dance` |

## 17. 替换映射

<details><summary>round-1：242 条（政治/宗教/数据/暴力/族群/金融）</summary>

| 原 | 新 |
|---|---|
| `alpha` | `alba` |
| `omega` | `alto` |
| `crown` | `amber` |
| `archon` | `amble` |
| `tenet` | `arbor` |
| `creed` | `ardor` |
| `avatar` | `aria` |
| `user` | `armor` |
| `buyer` | `aroma` |
| `client` | `aspen` |
| `ritual` | `aura` |
| `tribe` | `avian` |
| `crowd` | `azure` |
| `bias` | `babel` |
| `blind` | `bail` |
| `flaw` | `bale` |
| `error` | `bark` |
| `wrong` | `barn` |
| `person` | `baron` |
| `people` | `basil` |
| `human` | `basin` |
| `bound` | `bayou` |
| `record` | `bean` |
| `expose` | `beard` |
| `wash` | `beast` |
| `lazy` | `beech` |
| `worker` | `beetle` |
| `daemon` | `beige` |
| `union` | `berry` |
| `abort` | `bevel` |
| `native` | `birch` |
| `phone` | `bison` |
| `skin` | `blade` |
| `drill` | `blaze` |
| `hammer` | `bleak` |
| `fire` | `bless` |
| `mean` | `blimp` |
| `odds` | `blitz` |
| `chance` | `bluff` |
| `monte` | `blurb` |
| `carlo` | `blush` |
| `loss` | `boat` |
| `adam` | `bobbin` |
| `fuzz` | `bough` |
| `mock` | `bourn` |
| `smoke` | `bower` |
| `gray` | `brace` |
| `black` | `brass` |
| `white` | `brave` |
| `fault` | `brawn` |
| `dump` | `bread` |
| `crash` | `breeze` |
| `panic` | `brew` |
| `trap` | `briar` |
| `leak` | `brim` |
| `race` | `brine` |
| `stall` | `brisk` |
| `hang` | `brook` |
| `flake` | `broom` |
| `razor` | `broth` |
| `critic` | `bruise` |
| `jury` | `bubble` |
| `fail` | `buckle` |
| `secret` | `buff` |
| `token` | `bulb` |
| `risk` | `bumper` |
| `worm` | `bunch` |
| `phish` | `burl` |
| `spoof` | `bush` |
| `sniff` | `bustle` |
| `inject` | `butte` |
| `csrf` | `button` |
| `sqli` | `cabin` |
| `gdpr` | `cactus` |
| `ccpa` | `cadet` |
| `mask` | `cage` |
| `redact` | `cairn` |
| `anon` | `cake` |
| `bare` | `calf` |
| `block` | `callus` |
| `rocket` | `cameo` |
| `fleet` | `canal` |
| `alert` | `candle` |
| `alarm` | `canoe` |
| `budget` | `canopy` |
| `spend` | `canyon` |
| `cost` | `cape` |
| `price` | `caper` |
| `bill` | `carol` |
| `charge` | `cask` |
| `ledger` | `castle` |
| `siren` | `cater` |
| `profit` | `cavern` |
| `income` | `ceil` |
| `toll` | `cellar` |
| `rent` | `cement` |
| `hoard` | `censer` |
| `waste` | `chafe` |
| `burn` | `chaff` |
| `duty` | `chair` |
| `fiscal` | `chalk` |
| `tariff` | `chant` |
| `rebate` | `chapel` |
| `acid` | `chase` |
| `leader` | `chasm` |
| `rope` | `chaste` |
| `cuckoo` | `cheek` |
| `oracle` | `cheese` |
| `prowl` | `chef` |
| `loon` | `cherry` |
| `accent` | `chess` |
| `arabic` | `choir` |
| `hebrew` | `chorus` |
| `cyril` | `chrome` |
| `pidgin` | `chuck` |
| `creole` | `chum` |
| `thai` | `cider` |
| `hindi` | `cigar` |
| `urdu` | `cinder` |
| `farsi` | `cinema` |
| `tamil` | `circus` |
| `telugu` | `citrus` |
| `zulu` | `city` |
| `maori` | `clam` |
| `judge` | `clang` |
| `oath` | `clap` |
| `court` | `clash` |
| `decree` | `clasp` |
| `edict` | `claw` |
| `vote` | `cleat` |
| `ballot` | `cleft` |
| `census` | `clever` |
| `senate` | `cliff` |
| `caucus` | `cling` |
| `party` | `cloak` |
| `bloc` | `clod` |
| `league` | `clog` |
| `pledge` | `cloth` |
| `faith` | `clover` |
| `legal` | `clown` |
| `suit` | `clump` |
| `fraud` | `clutch` |
| `scam` | `coast` |
| `bribe` | `coat` |
| `cull` | `cobalt` |
| `guilt` | `cobble` |
| `fine` | `cobra` |
| `levy` | `cocoa` |
| `penal` | `coil` |
| `child` | `cola` |
| `master` | `collar` |
| `email` | `colon` |
| `mail` | `colt` |
| `inbox` | `comb` |
| `pardon` | `combat` |
| `grace` | `comic` |
| `mercy` | `comma` |
| `guest` | `conch` |
| `caller` | `cone` |
| `spirit` | `confer` |
| `friend` | `conga` |
| `herd` | `cook` |
| `flock` | `cool` |
| `rally` | `cope` |
| `money` | `copper` |
| `cash` | `cord` |
| `fund` | `cork` |
| `bank` | `corn` |
| `loan` | `cornet` |
| `debt` | `corona` |
| `stock` | `corpus` |
| `credit` | `corral` |
| `debit` | `corset` |
| `markup` | `cortex` |
| `wallet` | `cosmic` |
| `purse` | `cosmos` |
| `coffer` | `cotton` |
| `till` | `couch` |
| `coin` | `county` |
| `change` | `couple` |
| `fare` | `cousin` |
| `salary` | `cove` |
| `wage` | `coven` |
| `option` | `covet` |
| `vest` | `cozy` |
| `angel` | `crab` |
| `round` | `crack` |
| `raise` | `cradle` |
| `cents` | `cram` |
| `penny` | `crank` |
| `dime` | `crater` |
| `buck` | `crave` |
| `quid` | `crayon` |
| `yuan` | `craze` |
| `euro` | `cream` |
| `pound` | `create` |
| `franc` | `creek` |
| `rupee` | `creep` |
| `chief` | `crib` |
| `poach` | `cringe` |
| `exit` | `croak` |
| `resign` | `crock` |
| `retire` | `crocus` |
| `sever` | `crook` |
| `clan` | `cross` |
| `folk` | `crouch` |
| `owner` | `crow` |
| `hawker` | `crude` |
| `dealer` | `cruise` |
| `excise` | `crumb` |
| `drone` | `crunch` |
| `convoy` | `crush` |
| `public` | `crust` |
| `cartel` | `cuddle` |
| `treaty` | `cuff` |
| `unite` | `cumin` |
| `unify` | `cupola` |
| `colony` | `curd` |
| `joint` | `curfew` |
| `force` | `curl` |
| `whale` | `curry` |
| `labor` | `curt` |
| `dove` | `cute` |
| `storm` | `cymbal` |
| `harm` | `cynic` |
| `hurt` | `acorn` |
| `abuse` | `alder` |
| `attack` | `aloe` |
| `vice` | `aster` |
| `evil` | `bamboo` |
| `wall` | `brier` |
| `lamb` | `dahlia` |
| `pride` | `daisy` |
| `revere` | `ebony` |
| `genome` | `elder` |
| `gene` | `flora` |
| `virus` | `garden` |
| `bacter` | `hazel` |
| `toxin` | `heath` |
| `serum` | `holly` |
| `dose` | `laurel` |
| `crypto` | `lilac` |

</details>

<details><summary>round-2：40 条（保留字 + 灰色词）</summary>

| 原 | 新 |
|---|---|
| `scope` | `lily` |
| `focus` | `lotus` |
| `task` | `maple` |
| `read` | `meadow` |
| `list` | `myrtle` |
| `clear` | `nettle` |
| `status` | `orchid` |
| `pane` | `palm` |
| `send` | `petal` |
| `split` | `pine` |
| `bless` | `poplar` |
| `label` | `poppy` |
| `prompt` | `reed` |
| `agent` | `rose` |
| `test` | `shrub` |
| `bruise` | `sprig` |
| `idle` | `spruce` |
| `censer` | `thorn` |
| `chapel` | `twig` |
| `kanji` | `violet` |
| `hanzi` | `willow` |
| `pinyin` | `yarrow` |
| `latin` | `badger` |
| `greek` | `beagle` |
| `roman` | `beaver` |
| `hangul` | `boar` |
| `kana` | `bobcat` |
| `hira` | `camel` |
| `diet` | `cattle` |
| `export` | `cougar` |
| `import` | `coyote` |
| `combat` | `dragon` |
| `close` | `duck` |
| `karma` | `fawn` |
| `corona` | `fish` |
| `coven` | `flea` |
| `role` | `frog` |
| `done` | `gecko` |
| `wait` | `hare` |
| `doctor` | `hippo` |

</details>

## 18. 实测验证记录（编排者 × forge）

- forge 审核耗时 14m52s（max effort），复现哨兵回显误命中（0.009s 假匹配）→ 证实 §8 防回显必要。
- `agent wait` 两次超时（5m/7m）因长任务 → 证实 §8 默认超时需放宽 + 进度心跳。
- 用户写 w2:t1:p9，真实 pane id w2:p9 → 证实 §5 target 归一化。
- `herdr agent get hao-forge-team`→agent_not_found → 证实 label 非 herdr target，需 §5 解析。
- forge 核实：herdr 0.9.5 命令面正确；pane list 含 label、agent list 含 name/status/pane_id 可按 pane_id join；session.json/snapshots/log 保存 label → 零注册表机制成立（含 §7 resume 口径修正）；词表完整性通过；herdr agent name 规则 [a-z][a-z0-9_-]{0,31} live 唯一、agent start NAME 必填、agent rename 有 agent_name_taken。
