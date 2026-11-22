# herdr-agent-ops 设计稿 v3

> 状态：待 forge 复审 → 用户授权 · 日期：2026-11-22 · 分支：docs/herdr-agent-team-design
> v3：修复 forge round-2 全部问题（新 P0 匹配器 false-negative、restore adopt、per-machine 唯一、clear 顺序、baseline 可执行序列、task marker、锁降级、过度设计裁剪、词表 round-3）；新增「等待方式/长等待唤醒/终止」回应用户。

## 1. 背景与痛点
herdr 多 agent 协作：任务级等待缺失、名字不持久、取名难。详见 v1/v2。

## 2. 命名与调用
- skill `herdr-agent-ops`；CLI `hao`；受管 label 前缀 `hao-`。
- 调用：`${CLAUDE_SKILL_DIR}/scripts/hao`（Claude Code）或 PATH 安装；远端无 python3/hao 退化为手动打印哨兵。`hao doctor` 查 python3≥3.9 / herdr 版本 / HERDR_ENV / machine profile / resume 配置。
- 所有命令 `--json`（agent 解析）+ 人读默认；**`--progress`/日志走 stderr，不污染 --json**；`hao done` 例外：哨兵走 stdout 最后一行，JSON 走 stderr。

## 3. 关键决定
| 维度 | 决定 |
|---|---|
| 名字持久化 | 零注册表：`hao-` label 是我们控制的解耦角色槽位；herdr agent_name/resume 是 best-effort 非契约 |
| 任务协调状态 | **临时任务台账** `$XDG_STATE_HOME/hao/tasks/<shortid>.json`（token/target/caller/status），完成或取消即清理；**非名字注册表**，best-effort 单机，非分布式锁 |
| 命名 | `^[a-z]{4,6}$`，**per-machine 唯一**；一代号一 agent；scope 仅 label 注解 |
| 等待 | 默认哨兵（拆分令牌防回显 + 容忍 TUI 前缀 + 尾部校验 + 旧 token 预检）；另有生命周期/结果文件模式 |
| 长等待 | ask 默认异步；唤醒=回调注入 prompt / 宿主 scheduler / 可选 watch(experimental) |
| 终止 | cancel(幂等) / abort(--interrupt 用 send-keys esc/ctrl+c)；不关 pane 不停 server |
| 恢复时机 | 仅 skill 入口 restore；**不装 hook**（移除 SessionStart 选项）|
| 跨机器 | 封装 --machine；本机 machine list=[] 仅 stub，标注未端到端验证 |

## 4. 目录结构
```
herdr-agent-ops/
├── SKILL.md
├── scripts/hao
├── references/{names.md,protocol.md,restore.md}
└── tests/{test_hao.py,test_names.py,integration/}
```
（移除 names.local.md：自定义仅走 `--custom`，且 --custom 名同样过保留字/敏感校验。）

## 5. Target 解析
- `hao-...`→label；`w<N>:p<M>`→pane id（兼容 `w<N>:t<K>:p<M>` 归一化）；其他→live agent name。先解析到唯一 pane；零匹配 exit 3，多匹配 exit 6 需 `--pick`。
- 解析在目标机器做；ask 回显下一步用稳定 target（label/pane id）。
- **pane id 字母后缀与迁移**：herdr pane id 可含字母（w3:pB/pM），move 后 id 变；hao 不假设纯数字，迁移后用返回的新 id 或 label。

## 6. 命名模型
- agent name `^[a-z]{4,6}$` per-machine live 唯一；label `^hao-([a-z]{4,6})(?:-([a-z0-9][a-z0-9-]{0,11}))?$`，scope 1–12 仅小写/数字/连字符，label≤23。
- 一代号一 agent；scope 不进 name。`hao name` 预检**整台 machine** 所有 live names + 所有 workspace label role + stale 占位；冲突 exit 6。
- `hao name <target> <name> [--scope S]`：name **必填**（agent CLI 非 TTY，不做 input() 交互）；`--suggest` 自动选一个并打印。shell-only pane 只设 label；非 hao- label 需 --force。**先 label 后 agent name**；rename 失败留 label 交 restore。
- `hao clear <target>`：**先清 label 再清 name**（修正：避免 name 清成功 label 失败后被 restore 复活）；不动非 hao- label（除非 --force）；doctor 提示残留 name。

## 7. 持久化与 restore
口径：session.json 存 label+agent_name；`resume_agents_on_restore=true` 会恢复受支持 agent。label 是解耦槽位，herdr resume 是 best-effort。兜底场景：agent 退出/被替换、unsupported kind、resume=false/失败。

restore：
1. **scope 只决定恢复哪些 label**：默认当前 HERDR_WORKSPACE_ID，`--workspace`/`--all` 扩大。
2. **name 占用检查扫整台 machine**：所有 live agents + 所有 workspace 的 label role（per-machine 唯一）。跨 workspace 同名 → exit 6。
3. pre-flight plan：label→role/scope→pane→agent；检测 role 冲突/name 占用/startup pending/stale/非法。
4. **不自动选 winner**：同 role 多 pane 全部报歧义 exit 6 + 候选，`--pick <pane>` 只恢复被选者，其余保留 label 由 doctor 报冲突。自然序仅展示。
5. **默认 adopt 模式**：对 scope 内 hao- pane，把非空但不等价的 agent name 改为 label role（解决“agent start NAME 必填、用别名启动后 restore 跳过”的矛盾）；`--no-adopt` 回到只填无名；`--dry-run` 预览；非 hao- label 需 --force。
6. 幂等 + 部分失败报告（成功/失败/跳过）；处理 startup pending（等待/重试/报告）。
7. doctor 列 stale/invalid/dup label + 读 resume 配置；repurpose pane 前先 hao clear。真实 restart 测试用隔离 named session。

## 8. 等待协议（修 forge round-2 P0/P1）

### 8.1 哨兵防回显 + 防 false-negative
- token=`hao-<12–16hex>`；**task marker 用独立短 id** `[TASK <short8hex>]`，不含完整 token。prompt 把 token 拆两段，指令要求 peer 拼接后把 `HAO_DONE <token>` 作为最后一行打印。`hao ask` 扫描**整个最终 prompt**（任务文本+marker+哨兵指令）若含完整 token 则拒绝/改写。
- **匹配器容忍 TUI 前缀/缩进**（新 P0：Claude Code 续行缩进两空格、首行可能 ⏺/⎿）：默认 `pane wait-output --match "<full token>"`（token 唯一且预检不在 prompt/baseline），命中后校验位于快照尾部 N 行且与 HAO_DONE 相邻；回退正则 `^\s*(?:[⏺●✻│⎿]\s*)?HAO_DONE\s+<token>\s*$`。**必须用真实 agent 最终消息做正例测试**，不能只用列首合成 stdout。
- **baseline 可执行序列**（forge #4：wait-output 无 offset/seq，baseline 定位为“旧 token 预检”）：①生成 token→读快照确认完整 token 不存在，存在则重生成；②发拆分 token prompt；③可选等 [TASK shortid] 出现再读 baseline 确认 token 仍不存在；④--match 等待；⑤命中校验在尾部 N 行且不在发送前快照；若命中 baseline 旧 token→协议错误，不循环 wait。

### 8.2 等待方式（回应用户：不止哨兵）
`--mode`：
- `sentinel`（默认）：文本哨兵，协作信号非安全边界。
- `lifecycle`：`herdr agent wait --until idle/done/blocked`，server 侧高效，适合单轮任务；完成后按需读内容。
- `file`：peer 把结果写安全临时目录文件、只回路径；`hao result` 读取；等待=轮询文件存在。适合大输出。**跨机器默认 local-only**；--machine 下让 agent cat 到 pane 再读，路径限制在安全临时目录防任意读。
- （experimental，非核心）pane metadata 旁路：`herdr pane report-metadata --token hao_done=<token>` + 轮询 `pane get .tokens`；需 --source 集成，远端未必可用，列为未来选项。
- 不做“可插拔框架”抽象，就这三种文档化模式。

### 8.3 长等待与唤醒（回应用户）
- `hao ask` **默认异步**：立即返回 token+shortid，不阻塞；`--wait` 才内联等。
- 长任务不阻塞调用方。唤醒三选一：①**完成回调**：`hao ask --wake <caller-target>` 记入台账，peer 完成后由完成步骤向调用方 pane 注入 `herdr agent prompt <caller> "[HAO_WAKE] <shortid> done ..."` 唤醒；②**宿主 scheduler**：调用方（如 Claude Code ScheduleWakeup）定时复查 `hao wait --timeout <短>`，token 稳定可重复 wait；③`hao watch`（experimental，v3 可选）后台轮询台账并注入唤醒。
- 默认超时放宽（30m），`--timeout 0` 无限；`--progress` 心跳走 stderr。

### 8.4 终止与超时（回应用户）
- `hao cancel <token|shortid>`：台账标记 cancelled（幂等）；waiter 停止；**迟到哨兵忽略**。
- `hao abort <token> [--interrupt]`：cancel + 可选中断对端 `herdr agent send-keys <target> esc` 再 `ctrl+c`（中断当前轮）。**不关 pane、不停 server**。
- 超时 exit 4 + agent 状态 + 尾部 → 编排者决定重试/cancel/abort；blocked exit 5 → 交用户审批或 abort，绝不自动点审批；exited/pane closed exit 3。
- **一 pane 一 outstanding task 降级为 best-effort**：台账记 per-pane busy 供检查，但无分布式锁，调用方需自行避免并发；**移除 --queue**（无队列状态）。
- `hao done --token T [--summary]`：先 summary 后哨兵（stdout 最后一行）；须在 peer 自己 pane 运行；远端无 hao 按 prompt 手动打印。

## 9. 错误码映射
hao：0 成功/2 用法/3 target 不存在·exited·closed/4 超时/5 blocked/6 冲突·歧义·name taken/7 machine 不可用/8 herdr·server 错误/9 协议错误（baseline 旧 token 命中等）。
解析 herdr JSON error.code/stderr，不透传退出码。映射：agent_name_taken·agent_target_ambiguous→6；pane_not_found·agent_not_found→3；timeout→4；agent_blocked→5；unknown machine·no profile→7；agent_prompt_stalled·remote connection failure·**startup pending·invalid_agent_name**·其他 server error→8（startup pending 可重试等待）。mutating 不盲重试，区分没发出/可能已发出。

## 10. 跨机器
本机 machine list=[]，仅 stub，标注未端到端验证。--machine 不与 --session/--remote 组合；不传 --current/本地 ID。name/clear/suggest/list/restore/ask/wait/cancel/abort/result 均支持 --machine，target 解析在远端。doctor --machine 用 machine status 查 enabled/reachable/version；无/未知 profile→exit 7。远端 server 须运行且 API 兼容；连接失败≠mutation 未发生。**新命令 machine 语义**：台账按 machine 分键；cancel/abort/result 的 --machine 指向任务所在机器。

## 11. suggest
names.md 每组中英文关键词别名 + 确定性打分；任务文本→组；组耗尽→相邻组 fallback 或 --custom。“未占用”=**per-machine** 所有 live names + 所有 label role + stale 占位。**排除保留字**（§14 扩充集）；`--suggest` 非交互自动选一并打印；`hao suggest --json` 输出候选/组/理由；验收 3–5 中英文 task。

## 12. 五维优化（裁剪过度设计）
**功能**：name/restore/ask/wait/done/list/suggest/clear/doctor/status/say/result/cancel/abort；target 归一化、稳定 target 回显、--json。**移除/延后**：broadcast（多 target token/部分失败/聚合未定义，v3 范围外）、export/import（人工快照会 reintroduce stale state，延后到 v4 或定义 schema/preflight/冲突后再做）、可插拔等待框架（改三模式）、names.local.md（仅 --custom）、SessionStart hook（与仅入口冲突）、--queue、交互式 input() 取名。
**性能**：server 侧 wait-output 非忙轮询；--lines 限界；restore 单遍 pre-flight；suggest 静态索引。**rename 是循环非 batch API，不宣称批量优化**。
**容灾**：哨兵防回显+防 false-negative+旧 token 预检；blocked/exited/closed 立即返回；超时给状态+尾部；mutating 不盲重试；restore 幂等+部分失败报告；cancel 幂等忽略迟到哨兵；台账完成即清理；doctor 检 stale/invalid/dup+resume。
**扩展性**：--custom（过校验）；三等待模式；多 machine；agent-kind 无关；保留字过滤可配置。watch/metadata 旁路标 experimental。
**易用性**：hao 无参=帮助+roster 仪表盘；name 必填+--suggest；短别名；错误带下一步提示；mutating 全 --dry-run；doctor 可执行修复；--progress 走 stderr。

## 13. 安全性
不碰 server stop、不主动关 pane；只改 hao- label 与显式 target name；restore 默认当前 workspace + adopt 可控；非 hao- label 需 --force；跨机器先校验 profile 不猜 SSH host；不自动点审批；result 路径限安全临时目录。

## 14. 敏感审查（脚本化 + 具体政策）
deny/allow 落成规则 + `tests/test_names.py` **只断言可判定集合**（完整性 + 显式 deny + 保留字），不宣称“无灰色词”全覆盖。
- **保留字 deny（扩充）**：wait done list read test agent name ask clear doctor suggest status export import restore pane idle working blocked unknown hat hao herdr task token scope label role machine session tab workspace terminal send prompt focus split close attach config input layout move resize server start swap update open report view。
- **灰色 deny**：宗教/神秘 corona coven chapel censer bless karma creed faith oath angel spirit grace mercy pardon lamb dove revere saint fairy genie magic spell；暴力 combat bruise attack harm hurt abuse evil vice cull clash claw crack cringe crook crush；身体 diet beard brawn；族群/语言 greek roman latin kanji hanzi pinyin hangul kana hira hebrew arabic cyril thai hindi urdu farsi tamil telugu zulu maori。
- **allow-list（ documented 例外）**：文学/叙事 myth saga fable tale verse prose story lyric sonnet rhyme stanza；自然/动物/工具/颜色/材质/食物类中性词。理由：文学/自然术语非 occult/暴力/族群。
- round-3 替换 25 词（10 命令词 + open/report/view + 灰色 clash/claw/crack/cringe/crook/crush/beard/brawn/fairy/genie/magic/spell）。数据完整性：40×40=1600 唯一、全 4–6 小写、无保留字、无显式灰色词（脚本断言）。
- **round-1 表标注为历史**（其 target 在 round-2/3 已被再替换），不用于重建最终词表。

## 15. 验收（可测，修矛盾）
单元 stub + 集成 named test session（真实 split/set label/start agent/restore/ask/wait/cancel/abort，含 echo 与 TUI 缩进正例）。
1. `hao name w2:p9 hawk --scope api` → agent hawk + label hao-hawk-api
2. agent 退出后用**别名** `herdr agent start temp ...` 重开 → `hao restore`（默认 adopt）把 temp 改回 hawk；`--no-adopt` 则跳过
3. label=yaml 的 pane 不被 restore 触碰
4. 两 pane 都标 hao-hawk → **都报歧义 exit 6 不 rename**；`--pick <pane>` 只恢复被选者
5. 两 pane hao-hawk-api / hao-hawk-web → agent name hawk 冲突 exit 6（一代号一 agent）
6. **另一 workspace 已有 live agent hawk** → 本 workspace restore/name exit 6（per-machine 唯一）
7. ask/wait：预置哨兵或 prompt 回显时 wait 不得成功；**真实 agent 最终消息（含 TUI 缩进/⏺ 前缀）能被匹配**（正例）；仅新打印哨兵算完成
8. machine：fixture 覆盖 list 两 shape/unknown profile/remote down/machine+session；本机无 profile 标注未验证
9. suggest：3–5 中英文 task；live 重名=扫 agent names+all labels+stale
10. cancel 幂等、迟到哨兵忽略；abort --interrupt 发 esc/ctrl+c 不关 pane；超时 exit 4 带状态+尾部；blocked exit 5
11. test_names.py：完整性+保留字+显式 deny 断言

## 16. 名字词表（40×40，round-3 后）
| # | 分工 | 主题 | 40 候选 |
|---|---|---|---|
| 1 | 规划编排 | 地图/方向/星光/秩序 | `atlas` `north` `lumen` `vega` `orion` `polar` `lyra` `aegis` `ethos` `prime` `alba` `alto` `amber` `axis` `order` `logic` `arch` `amble` `nova` `aurora` `vision` `intent` `arbor` `ardor` `vista` `rudder` `tack` `spire` `apex` `summit` `zenith` `peak` `crest` `cycle` `phase` `stage` `step` `scheme` `tactic` `method` |
| 2 | 需求产品 | 价值/用户/市场/目标 | `value` `worth` `lily` `brief` `pitch` `angle` `lotus` `demand` `offer` `solve` `case` `aria` `listen` `market` `growth` `trend` `goal` `core` `first` `seed` `need` `want` `wish` `must` `armor` `aroma` `aspen` `survey` `niche` `epic` `maple` `ticket` `beta` `pilot` `launch` `deck` `deal` `query` `agile` `sprint` |
| 3 | 用户研究 | 观察/倾听/行为/群体 | `study` `learn` `sense` `feel` `mood` `quote` `heat` `funnel` `drop` `churn` `retain` `habit` `aura` `cohort` `panel` `poll` `group` `circle` `avian` `azure` `field` `shadow` `notice` `meadow` `talk` `chat` `reply` `depth` `broad` `narrow` `babel` `bail` `spot` `bale` `bark` `barn` `baron` `basil` `basin` `mind` |
| 4 | 架构接口 | 结构/边界/契约/骨架 | `frame` `shell` `layer` `bayou` `proto` `module` `plugin` `spine` `base` `form` `shape` `span` `dome` `vault` `keel` `mast` `pillar` `column` `scale` `plane` `beam` `girder` `joist` `rafter` `lintel` `corbel` `plinth` `atrium` `facade` `link` `schema` `driver` `model` `object` `entity` `bean` `tree` `heap` `myrtle` `trie` |
| 5 | 设计体验 | 色彩/形态/笔触/韵律 | `muse` `iris` `opal` `forma` `motif` `verve` `poise` `glint` `bloom` `tint` `tone` `shade` `brush` `easel` `craft` `sculpt` `chisel` `etude` `lyric` `sonnet` `draft` `wire` `hornet` `space` `align` `margin` `border` `radius` `ombre` `glow` `matte` `glass` `frost` `noise` `grain` `stripe` `color` `chroma` `swatch` `icon` |
| 6 | 视觉品牌 | 标识/排版/质感/风格 | `brand` `logo` `mark` `emblem` `badge` `sigil` `banner` `poster` `flyer` `cover` `spread` `type` `serif` `sans` `font` `weight` `italic` `bold` `light` `heavy` `gothic` `rhythm` `photo` `crop` `blur` `sharp` `horse` `filter` `gloss` `satin` `linen` `paper` `paint` `stroke` `beast` `deco` `retro` `modern` `clean` `subtle` |
| 7 | 前端体验 | 交互/动效/组件/界面 | `cursor` `click` `touch` `swipe` `motion` `anim` `ease` `flow` `fluid` `smooth` `crisp` `nettle` `glide` `slide` `shift` `hover` `canvas` `sketch` `menu` `theme` `render` `reflow` `bundle` `chunk` `beech` `fetch` `state` `store` `props` `hook` `jackal` `toggle` `slider` `picker` `modal` `toast` `card` `drawer` `sheet` `dialog` |
| 8 | 后端服务 | 服务/队列/协议/并发 | `serve` `route` `queue` `beetle` `cron` `beige` `socket` `stream` `buffer` `pipe` `broker` `router` `kitten` `engine` `retry` `batch` `async` `event` `shard` `raft` `topic` `pubsub` `fanout` `rest` `grpc` `soap` `http` `cookie` `header` `body` `orchid` `code` `koala` `join` `berry` `offset` `commit` `bevel` `lease` `atomic` |
| 9 | 移动桌面 | 触控/设备/离线/同步 | `mobile` `birch` `hybrid` `tablet` `bison` `wear` `haptic` `vibe` `shake` `tilt` `rotate` `orient` `screen` `palm` `tray` `widget` `hotkey` `pull` `stash` `online` `sync` `local` `remote` `push` `notify` `power` `drain` `sleep` `wake` `resume` `pause` `play` `retina` `inset` `notch` `keypad` `share` `petal` `blade` `lemur` |
| 10 | 实现构建 | 锻造/金属/结构/火 | `forge` `flint` `ember` `anvil` `cedar` `kiln` `steel` `iron` `bolt` `gear` `lever` `pylon` `truss` `brick` `mortar` `weld` `solder` `alloy` `smelt` `hearth` `cast` `mold` `mint` `carve` `lathe` `mill` `blaze` `clamp` `vise` `file` `rasp` `bleak` `wrench` `pliers` `ruler` `tape` `glue` `epoxy` `resin` `clay` |
| 11 | 数据工程 | 管道/存储/格式/血缘 | `ingest` `dedupe` `enrich` `merge` `pine` `arrow` `avro` `json` `yaml` `lake` `pond` `mart` `cube` `fact` `star` `snow` `origin` `source` `target` `sink` `spigot` `faucet` `valve` `null` `blank` `empty` `dupe` `stale` `fresh` `late` `drift` `skew` `sched` `poplar` `backup` `save` `loader` `parser` `mapper` `sorter` |
| 12 | 数据科学 | 统计/推断/图表/概率 | `stats` `blimp` `median` `range` `quart` `season` `factor` `latent` `poppy` `train` `score` `rank` `topk` `lizard` `infer` `causal` `effect` `impact` `lift` `uplift` `pivot` `slice` `dice` `rollup` `plot` `legend` `tick` `bins` `blitz` `bluff` `prior` `bayes` `markov` `blurb` `blush` `random` `resid` `ridge` `lasso` `gini` |
| 13 | 机器学习 | 模型/训练/推理/神经 | `neuron` `neural` `boat` `epoch` `embed` `reed` `window` `rose` `reward` `action` `head` `norm` `relu` `tanh` `gelu` `lstm` `unet` `lora` `qlora` `peft` `rlhf` `search` `grad` `bobbin` `warmup` `prune` `sparse` `dense` `tune` `steer` `logit` `spike` `micro` `macro` `fold` `expert` `small` `large` `tiny` `giant` |
| 14 | 测试实验 | 试验/基准/模糊/金丝雀 | `trial` `sample` `bench` `bough` `assert` `expect` `bourn` `stub` `suite` `golden` `bower` `canary` `chaos` `stress` `load` `surge` `burst` `quota` `metric` `grade` `shrub` `verify` `plan` `setup` `before` `after` `unit` `brace` `brass` `brave` `happy` `corner` `flaky` `line` `branch` `soak` `perf` `blue` `green` `check` |
| 15 | 调试修复 | 追踪/探针/疗愈/修补 | `hound` `trace` `probe` `spark` `rivet` `mend` `heal` `cure` `balm` `salve` `suture` `splint` `remedy` `tinker` `patch` `clue` `trail` `track` `llama` `ferret` `bisect` `repro` `bread` `breeze` `brew` `warn` `root` `cause` `reason` `hotfix` `reduce` `shrink` `marten` `briar` `brim` `brine` `brisk` `brook` `loop` `broom` |
| 16 | 验证审阅 | 锐眼/量具/证明/守卫 | `hawk` `lens` `prism` `ward` `proof` `verity` `broth` `edge` `sift` `trust` `gauge` `plumb` `level` `square` `assay` `valid` `scan` `sweep` `shield` `lynx` `glance` `peer` `skim` `sprig` `bubble` `spec` `canon` `stamp` `pass` `buckle` `veto` `assent` `ruling` `appeal` `patrol` `scout` `ranger` `vigil` `look` `rule` |
| 17 | 安全隐私 | 锁/密钥/防护/威胁 | `guard` `lock` `crypt` `buff` `bulb` `permit` `policy` `safe` `secure` `seal` `sign` `auth` `login` `access` `grant` `deny` `threat` `bumper` `sentry` `moat` `hash` `salt` `nonce` `hmac` `vuln` `bunch` `burl` `bush` `bustle` `butte` `button` `cabin` `zero` `least` `purple` `cactus` `cadet` `cage` `cairn` `cake` |
| 18 | 基础设施 | 云/网络/存储/平台 | `cloud` `infra` `deploy` `subnet` `switch` `tunnel` `egress` `packet` `swarm` `hive` `host` `image` `volume` `disk` `mount` `blob` `bucket` `pool` `mirror` `memory` `hyper` `calf` `metal` `chip` `board` `fabric` `vlan` `vxlan` `dhcp` `ipam` `cidr` `ospf` `mpls` `callus` `mole` `init` `monkey` `param` `cert` `jump` |
| 19 | 发布运维 | 信标/港湾/航行/信号 | `beacon` `harbor` `anchor` `helm` `pulse` `signal` `watch` `port` `dock` `gate` `tower` `keep` `ferry` `orbit` `comet` `cameo` `radar` `sonar` `buoy` `canal` `ship` `revert` `moth` `bump` `repo` `binary` `dist` `prod` `sanity` `undo` `redo` `freeze` `thaw` `flag` `health` `vendor` `roll` `stable` `latest` `pinned` |
| 20 | 监控成本 | 告警/预算/计量/节俭 | `candle` `canoe` `canopy` `canyon` `cape` `limit` `rate` `util` `usage` `caper` `carol` `cask` `castle` `cater` `stat` `tally` `count` `spruce` `thrift` `frugal` `dash` `uptime` `floor` `cavern` `ceil` `cellar` `cement` `thorn` `chafe` `chaff` `spare` `oncall` `pager` `chair` `rota` `quiet` `silent` `chalk` `chant` `twig` |
| 21 | 网络通信 | 协议/信号/传输/连接 | `https` `smtp` `imap` `sftp` `mqtt` `amqp` `coap` `quic` `radio` `wave` `fiber` `coax` `cable` `ping` `pong` `call` `dial` `ring` `beep` `buzz` `feed` `cell` `slot` `band` `modem` `codec` `demux` `parley` `chirp` `squawk` `shout` `speak` `flare` `uplink` `roam` `tether` `pair` `bond` `hail` `blink` |
| 22 | 存储检索 | 索引/结构/容器/查找 | `folder` `seek` `find` `lookup` `match` `sort` `btree` `mvcc` `chase` `crdt` `paxos` `chasm` `mmap` `cold` `warm` `tier` `hnsw` `chaste` `radix` `octree` `extent` `inode` `dentry` `vacuum` `parse` `format` `cheek` `fifo` `lifo` `pack` `shelf` `rack` `locker` `chest` `crate` `pallet` `carton` `desk` `closet` `spool` |
| 23 | 研究检索 | 智慧/索引/解密/探索 | `sage` `index` `cipher` `quest` `raven` `wren` `lark` `finch` `heron` `swift` `robin` `magpie` `merlin` `cheese` `rune` `lore` `riddle` `enigma` `lexis` `path` `browse` `chef` `delve` `scent` `eagle` `falcon` `osprey` `condor` `kite` `stork` `ibis` `egret` `swan` `goose` `teal` `cherry` `gull` `tern` `puffin` `petrel` |
| 24 | 文档表达 | 书写/诗行/故事/清晰 | `quill` `verse` `fable` `glyph` `tome` `prose` `story` `voice` `echo` `page` `leaf` `scroll` `rhyme` `stanza` `meter` `chess` `phrase` `syntax` `lucid` `memo` `write` `edit` `copy` `paste` `clip` `note` `digest` `title` `style` `term` `jargon` `slang` `cite` `claim` `essay` `blog` `post` `book` `issue` `figure` |
| 25 | 本地化翻译 | 语言/文字/区域/文化 | `locale` `lingua` `verb` `noun` `script` `violet` `willow` `yarrow` `badger` `beagle` `beaver` `choir` `chorus` `chrome` `text` `word` `clause` `idiom` `tongue` `globe` `global` `region` `zone` `area` `custom` `chuck` `chum` `char` `ascii` `boar` `bobcat` `camel` `cider` `cigar` `cinder` `cinema` `circus` `citrus` `city` `clam` |
| 26 | 合规治理 | 议事/契约/裁决/秩序 | `nexus` `envoy` `herald` `relay` `clang` `bridge` `warden` `keeper` `forum` `agora` `quorum` `proxy` `accord` `truce` `pact` `clap` `civic` `polis` `realm` `mouse` `ethic` `moral` `clasp` `newt` `cleat` `cleft` `clever` `cliff` `cattle` `house` `cling` `cloak` `clod` `clog` `peace` `cloth` `clover` `honor` `equity` `fair` |
| 27 | 法务风控 | 法律/合同/风险/保险 | `clown` `clump` `terms` `breach` `waiver` `patent` `docket` `hedge` `damage` `clutch` `coast` `coat` `cobalt` `cougar` `coyote` `will` `estate` `heir` `settle` `defend` `accuse` `plead` `cobble` `alibi` `motive` `notary` `clerk` `scribe` `assure` `insure` `surety` `cobra` `cocoa` `coil` `liable` `caveat` `umpire` `deed` `lien` `escrow` |
| 28 | 教学讲解 | 导师/课程/练习/启发 | `tutor` `mentor` `coach` `guide` `lesson` `course` `class` `quiz` `exam` `hint` `demo` `show` `tell` `wonder` `answer` `simple` `plain` `skill` `repeat` `recall` `teach` `myth` `tale` `saga` `school` `campus` `studio` `ponder` `think` `recap` `flash` `praise` `tweak` `easy` `hard` `vivid` `cola` `novice` `collar` `mentee` |
| 29 | 支持成功 | 帮助/关怀/响应/忠诚 | `help` `care` `assist` `rescue` `smile` `kind` `nice` `calm` `soothe` `triage` `assign` `refer` `loyal` `greet` `colon` `colt` `comb` `thread` `video` `glad` `cheer` `sorry` `dragon` `comic` `comma` `conch` `cone` `manual` `howto` `please` `otter` `inform` `advise` `portal` `center` `heart` `hope` `confer` `hand` `conga` |
| 30 | 销售市场 | 交易/推广/渠道/激励 | `sell` `sale` `duck` `lead` `promo` `social` `viral` `hype` `news` `press` `asset` `media` `free` `resell` `distro` `reach` `coupon` `upsell` `cart` `basket` `shop` `retail` `bazaar` `mall` `booth` `stand` `engage` `tend` `site` `maker` `champ` `bounty` `bonus` `gift` `prize` `award` `medal` `points` `outlet` `kiosk` |
| 31 | 内容社交 | 媒体/社区/互动/创作 | `vlog` `reel` `short` `live` `like` `follow` `handle` `emoji` `upvote` `fawn` `club` `guild` `team` `crew` `squad` `cook` `cool` `scene` `beat` `tempo` `chord` `melody` `song` `audio` `zine` `onair` `meet` `meetup` `camp` `gather` `cope` `game` `arcade` `puzzle` `trivia` `kudos` `tile` `flair` `about` `mosaic` |
| 32 | 财务计费 | 货币/账务/薪酬/投资 | `copper` `cord` `cork` `corn` `cornet` `fish` `corpus` `corral` `corset` `entry` `annual` `month` `week` `paid` `gross` `cortex` `cosmic` `cosmos` `cotton` `couch` `county` `couple` `cousin` `cove` `flea` `covet` `cozy` `crab` `panda` `cradle` `cram` `crank` `crater` `crave` `crayon` `craze` `cream` `create` `creek` `creep` |
| 33 | 人力招聘 | 人才/职业/团队/流动 | `talent` `hire` `staff` `career` `ladder` `frog` `review` `rubric` `folio` `buddy` `morale` `perk` `values` `office` `seat` `room` `apply` `intern` `junior` `senior` `crib` `parrot` `ally` `croak` `crock` `crocus` `pigeon` `leave` `break` `repose` `roster` `swing` `flex` `temp` `perm` `cross` `crouch` `nest` `roost` `burrow` |
| 34 | 项目管理 | 进度/看板/节奏/交付 | `scrum` `wrap` `gantt` `todo` `gecko` `doing` `crow` `time` `date` `work` `urgent` `major` `minor` `point` `size` `agenda` `item` `lane` `swim` `slack` `float` `fast` `slow` `speed` `pace` `weekly` `daily` `clock` `timer` `bell` `remind` `next` `last` `kick` `begin` `pike` `ready` `park` `hold` `hare` |
| 35 | 采购供应链 | 物流/仓储/运输/交易 | `supply` `tender` `cargo` `depot` `yard` `quay` `berth` `crane` `fork` `hoist` `chute` `belt` `roller` `seller` `crude` `trader` `cruise` `haggle` `bulk` `sack` `tote` `skid` `truck` `rail` `crumb` `safety` `pick` `haul` `unload` `crunch` `robot` `convey` `lading` `tanker` `barge` `vessel` `pony` `drum` `pier` `wharf` |
| 36 | 生态合作 | 连接/共生/联盟/共享 | `place` `crust` `addon` `biome` `mutual` `coop` `cuddle` `cuff` `invest` `spoke` `axle` `door` `give` `trade` `barter` `lend` `borrow` `cumin` `cupola` `grove` `forest` `reef` `coral` `kelp` `moss` `fern` `vine` `shoal` `curd` `knot` `weave` `braid` `strand` `curfew` `shared` `common` `cohost` `clone` `curate` `merit` |
| 37 | 战略分析 | 框架/决策/竞争/格局 | `swot` `pest` `porter` `five` `curl` `chain` `life` `choice` `thesis` `assume` `lean` `wedge` `ocean` `weak` `assess` `turn` `puma` `stake` `return` `yield` `bull` `bear` `lion` `tiger` `shark` `curry` `beach` `stance` `codex` `firm` `curt` `land` `cute` `wolf` `orca` `arena` `turf` `sector` `domain` `basis` |
| 38 | 创意灵感 | 想象/新奇/玩心/火花 | `idea` `dream` `cymbal` `whim` `fancy` `novel` `unique` `rare` `weird` `wild` `dare` `draw` `doodle` `mash` `blend` `remix` `twist` `flip` `bend` `puppy` `quail` `rabbit` `rhino` `charm` `joke` `quip` `jest` `jolly` `merry` `zest` `bang` `boom` `fizz` `zing` `neon` `improv` `adlib` `riff` `solo` `encore` |
| 39 | 伦理安全 | 伤害/美德/诚实/守护 | `cynic` `acorn` `alder` `misuse` `aloe` `harden` `virtue` `aster` `good` `bamboo` `truth` `honest` `candor` `opaque` `curb` `brake` `right` `wisdom` `aware` `attune` `heed` `just` `equal` `same` `candid` `frank` `cred` `brier` `dahlia` `gentle` `still` `meek` `humble` `modest` `daisy` `blame` `shame` `regard` `esteem` `ebony` |
| 40 | 领域专家 | 医学/科学/工程/艺术 | `medic` `vital` `juris` `earth` `chem` `astro` `math` `clinic` `pharma` `elder` `flora` `neuro` `cardio` `derma` `onco` `renal` `immune` `garden` `hazel` `heath` `holly` `laurel` `nurse` `hippo` `econ` `devops` `lilac` `mecha` `aero` `auto` `civil` `struct` `mechan` `elect` `optic` `editor` `music` `visual` `film` `dance` |

## 17. 替换映射
<details><summary>round-1（历史，242 条，target 已被后续再替换，勿用于重建）</summary>

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

<details><summary>round-2（40 条）</summary>

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

<details><summary>round-3（25 条）</summary>

| 原 | 新 |
|---|---|
| `layout` | `hornet` |
| `beard` | `horse` |
| `input` | `jackal` |
| `server` | `kitten` |
| `view` | `koala` |
| `start` | `lemur` |
| `report` | `lizard` |
| `brawn` | `llama` |
| `attach` | `marten` |
| `resize` | `mole` |
| `config` | `monkey` |
| `swap` | `moth` |
| `clash` | `mouse` |
| `claw` | `newt` |
| `update` | `otter` |
| `crack` | `panda` |
| `cringe` | `parrot` |
| `crook` | `pigeon` |
| `open` | `pike` |
| `crush` | `pony` |
| `move` | `puma` |
| `fairy` | `puppy` |
| `genie` | `quail` |
| `magic` | `rabbit` |
| `spell` | `rhino` |

</details>

## 18. 实测验证记录
- round-1：forge 14m52s 复现哨兵回显误命中（0.009s 假匹配）。
- round-2：forge 9m29s；**编排者用 ^HAO_DONE 等待真实完成行超时（false-negative）**，forge 预言并证实 TUI 缩进/⏺ 前缀导致行首锚定失配 → v3 改 --match 完整 token + 尾部校验 + 容忍前缀回退。拆分令牌 prompt 级防回显经 forge 脚本验证生效（完整 token 不在 prompt）。
- agent wait 两次超时（长任务）→ 默认超时放宽 + 异步 ask + 唤醒。
- w2:t1:p9 vs w2:p9 → target 归一化；herdr agent get <label>→agent_not_found → label 需先解析。
- forge 核实：herdr 0.9.5 命令面正确；pane list 含 label、agent list 含 name/status/pane_id 可 join；session.json/snapshots/log 保存 label；词表完整性通过；agent name [a-z][a-z0-9_-]{0,31} live 唯一、agent start NAME 必填、agent rename 有 agent_name_taken；wait-output --regex ^ 已按行匹配（无需 (?m)）。
