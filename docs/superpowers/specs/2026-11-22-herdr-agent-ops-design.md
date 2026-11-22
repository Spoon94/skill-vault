# herdr-agent-ops 设计稿 v4

> 状态：待 forge 复审 → 用户授权 · 2026-11-22 · 分支 docs/herdr-agent-team-design
> v4：完整定义 forge round-3 的 10 条（canonical 完成路径、台账位置/清理/权限/降级、cancel 停阻塞 wait、lifecycle working 门槛、file 原子写/local-only、wake 固定模板/best-effort、abort 审批保护、watch 保留字 round-4、措辞、错误码与逐模式验收）。实验项明确标注、不影响 sentinel 主路径验收。

## 1. 背景
herdr 多 agent：任务级等待缺失、名字不持久、取名难。

## 2. 命名与调用
- skill `herdr-agent-ops`；CLI `hao`；label 前缀 `hao-`。调用 `${CLAUDE_SKILL_DIR}/scripts/hao` 或 PATH；远端无 python3/hao 退化手动打印。doctor 查 python3≥3.9/herdr/HERDR_ENV/machine/resume。
- `--json`+人读；`--progress`/日志走 stderr；`hao done` 哨兵走 stdout 最后一行、JSON 走 stderr。

## 3. 关键决定（措辞修正）
- **名字映射零注册表**：`hao-` label 是唯一名字载体（herdr session.json 保存 label；agent_name/resume 是 best-effort 非契约）。
- **任务协调用可清理的临时台账**（非名字注册表）：`$XDG_STATE_HOME/hao/tasks/<shortid>.json`，默认 `~/.local/state/hao/tasks`（XDG_STATE_HOME 未设时），目录 0700 文件 0600，绝对路径+realpath 校验。字段：token/shortid/target/machine/caller/mode/status/created/waiter_pid。**token 落盘**（token 非秘密，但不再声称“不落盘”）。原子写（temp+rename）+ per-shortid 锁；完成/取消即清理；无 waiter 的 async 任务 TTL（默认 24h）+ doctor 清 stale；**台账写失败降级**：hao ask 继续发送但禁用 wake/cancel 并警告（`--strict-ledger` 则报错）。
- 命名 `^[a-z]{4,6}$` per-machine 唯一；一代号一 agent；scope 仅 label 注解。
- 等待默认 sentinel；**canonical 完成=peer 在最终 assistant 消息打印哨兵**（见 §8.1）。长等待 ask 异步+唤醒；终止 cancel/abort。恢复仅 skill 入口，不装 hook。跨机器本机无 profile 仅 stub。

## 4. 目录
```
herdr-agent-ops/{SKILL.md,scripts/hao,references/{names,protocol,restore}.md,tests/{test_hao,test_names}.py+integration/}
```
自定义仅 --custom（过保留字/敏感校验）；无 names.local.md。

## 5. Target 解析
`hao-`→label；`w<N>:p<M>`→pane id（兼容 w:t:p 归一化）；其他→live name。唯一 pane；零匹配 exit3，多匹配 exit6 需 --pick。目标机器解析；ask 回显稳定 target。pane id 可含字母（w3:pB），move 后 id 变，用新 id/label。

## 6. 命名模型
name `^[a-z]{4,6}$` per-machine 唯一；label `^hao-([a-z]{4,6})(?:-([a-z0-9][a-z0-9-]{0,11}))?$`，scope 1–12 小写/数字/连字符，label≤23。一代号一 agent；hao name 预检整台 machine 所有 live names+所有 workspace label role+stale；冲突 exit6。name 必填（非 TTY 不 input()），--suggest 自动选一并打印。shell-only 只设 label；非 hao- label 需 --force。**先 label 后 name**，rename 失败留 label 交 restore。**clear 先 label 后 name**；不动非 hao- label（除非 --force）；doctor 提示残留 name。

## 7. restore
口径：session.json 存 label+agent_name；resume_agents_on_restore=true 恢复受支持 agent；label 是解耦槽位。兜底：退出/被替换/unsupported/resume=false/失败。
1. scope 只决定恢复哪些 label（默认当前 workspace，--workspace/--all 扩大）。
2. **name 占用扫整台 machine**（所有 live agents+所有 workspace label role）；跨 workspace 同名 exit6。
3. pre-flight：label→role/scope→pane→agent；检测冲突/占用/startup pending/stale/非法。
4. **不自动选 winner**：同 role 多 pane 全报歧义 exit6+候选，--pick 只恢复被选者，其余留 label 由 doctor 报冲突。
5. **默认 adopt**：scope 内 hao- pane 把非空不等价 name 改为 role；--no-adopt 只填无名（注：agent start 必有名，--no-adopt 实际只覆盖手动启动的无名 agent）；--dry-run 预览；非 hao- 需 --force。
6. 幂等+部分失败报告；startup pending 等待/重试/报告。doctor 列 stale/invalid/dup+resume；repurpose 前先 clear；restart 测试用隔离 named session。

## 8. 等待协议
### 8.1 canonical 完成路径（forge round-3 #1，实测）
- **可靠路径=peer 在最终 assistant 消息里打印 `HAO_DONE <token>`**。forge 实测：Claude Code 的 Bash tool stdout **不进 pane snapshot**（pane read 只见 tool-call 源码），故 `hao done` 若经 Bash tool 执行，wait 可能永远看不到。
- `hao done` 文档注明：**仅当 agent 把 tool stdout 渲染到 pane 时有效**；canonical 是最终消息打印。prompt 指令要求 peer 在最终消息最后一行打印哨兵。
- 验收新增：真实 agent 经 Bash 跑 hao done → wait 看不到（记录为已知限制）；最终消息打印 → wait 命中。
- 防回显：token=hao-<12–16hex>；task marker 用短 id `[TASK <short8hex>]` 不含完整 token；prompt 拆 token 两段令 peer 拼接；hao ask 扫描整个最终 prompt 含完整 token 则拒绝/改写。
- 匹配：默认 `pane wait-output --match "<full token>"`（字面 substring，容忍 TUI 两空格/⏺ 前缀），命中校验尾部 N 行+HAO_DONE 邻接；回退正则 `^\s*(?:[⏺●✻│⎿]\s*)?HAO_DONE\s+<token>\s*$`。真实 agent 最终消息正例测试。
- baseline 五步（旧 token 预检，非 offset）：①生成 token→读快照确认不存在否则重生成；②发拆分 prompt；③可选等 [TASK shortid] 再读 baseline 确认 token 不存在；④--match 等待；⑤命中校验尾部+不在发送前快照；命中 baseline 旧 token→协议错误 exit9 不循环。
### 8.2 等待模式
- `sentinel`（默认，核心）：上述。
- `lifecycle`：**working 门槛**——提交后必须观察到 working/blocked（用 agent prompt --wait 的 5s 门槛），否则不算完成；仅适合单轮且提交时 agent 从非 working 开始；agent 已 working 时不得把当前 turn 完成当本任务完成。防“已 idle 立即返回假完成”。
- `file`：**local-only**；peer 原子写（temp+rename）或文件内完成标记/长度校验，防 partial（存在≠写完）；hao result 限 hao ask 创建的安全临时目录，realpath+防 symlink/穿越。跨机器 cat-to-pane 与 #1 同问题不可靠→**experimental/不支持**；--machine 下仅支持 peer 在最终消息返回路径/内容。
- metadata 旁路（report-metadata token）：**experimental**，需 --source，非核心。
- 不做可插拔框架，就 sentinel/lifecycle/file 三模式 + 实验项。
### 8.3 长等待与唤醒
- ask 默认异步立即返回 token+shortid；--wait 才内联。默认超时 30m，--timeout 0 无限；--progress 心跳 stderr。
- **台账 caller-local + machine 键**；跨机器 wake/cancel 由 caller 侧 poll（远端无 hao 也能用）。
- 唤醒：①`--wake <caller-target>` 完成时注入**固定模板** `herdr agent prompt <caller> "[HAO_WAKE] <shortid> <status>"`（**不含 peer summary**，防不可信输出注入；调用方自己 hao result/wait 读内容）；caller blocked→agent_blocked wake 丢失（best-effort）；caller working 可能排队。②**宿主 scheduler**（如 ScheduleWakeup）定时复查 hao wait --timeout 短，token 稳定可重复 wait（主 fallback）。③`hao watch` **experimental**：--once/超时/幂等/清理，非隐性 daemon，无验收不承诺。
### 8.4 终止与超时
- **hao wait 内部短超时轮询**（每 5–10s 一次 server wait-output）+ 每轮查台账 → cancel 能停下阻塞 wait。**cancelled wait exit10**（区别于 timeout 4）。
- `hao cancel <token|shortid>`：只标台账 cancelled（幂等，**不碰 peer**）；waiter 停；迟到哨兵忽略；**cancel 后 hao done 不得标 done**。
- `hao abort <token> [--interrupt]`：cancel + 可选发键 `herdr agent send-keys <target> esc`→`ctrl+c`。**blocked 下 --interrupt 需 --force/二次确认**（esc/ctrl+c 可能丢弃审批内容，文档明示）；不关 pane 不停 server。cancel 与 abort 语义分开。
- 超时 exit4+状态+尾部→编排者决定重试/cancel/abort；blocked exit5→交用户审批或 abort，绝不自动点审批；exited/closed exit3。
- 一 pane 一 task **best-effort**（台账记 busy，无分布式锁，调用方自行避免并发）；无 --queue。
- `hao done --token T [--summary]`：先 summary 后哨兵（stdout 最后一行）；须在 peer pane 且渲染到 pane 才有效（见 8.1）；远端无 hao 手动打印。

## 9. 错误码
0 成功/2 用法（含 **invalid_agent_name**）/3 target 不存在·exited·closed·result 文件不存在/4 超时/5 blocked/6 冲突·歧义·name taken/7 machine 不可用/8 herdr·server 错误（agent_prompt_stalled·remote failure·agent_not_ready·agent_pane_not_found·stale_pane_target·invalid_agent_timeout·watch 失败·台账损坏/不可写）/9 协议错误（baseline 旧 token）/10 cancelled。startup pending 可重试等待。解析 herdr JSON error.code/stderr 不透传；mutating 不盲重试。

## 10. 跨机器
本机 machine list=[] 仅 stub 标注未验证。--machine 不与 --session/--remote 组合，不传 --current/本地 ID。name/clear/suggest/list/restore/ask/wait/cancel/abort/result 支持 --machine，target 远端解析。doctor --machine 用 machine status；无/未知 profile exit7。台账 caller-local+machine 键，caller 侧 poll。file 跨机器 experimental。远端 server 须运行 API 兼容；连接失败≠未发生。

## 11. suggest
每组中英文关键词别名+确定性打分；组耗尽→相邻组/--custom。未占用=per-machine 所有 live names+所有 label role+stale。排除保留字（§14 全命令面）；--suggest 非交互；--json 候选/组/理由；验收 3–5 中英文 task。

## 12. 五维（裁剪+实验项标注）
功能：name/restore/ask/wait/done/list/suggest/clear/doctor/status/say/result/cancel/abort+target 归一化+稳定回显+--json。延后 broadcast/export-import（v4+）；去掉可插拔框架/names.local/hook/交互式 input/--queue。**watch/metadata 旁路/file 跨机器/--wake 跨机器=experimental，无验收不承诺，不影响 sentinel 主路径**。
性能：server 侧 wait-output（短超时轮询兼顾 cancel）；--lines 限界；restore 单遍 pre-flight；suggest 静态索引；rename 是循环非 batch。
容灾：防回显+防 false-negative+旧 token 预检；blocked/exited/closed 立即返回；超时给状态+尾部；mutating 不盲重试；restore 幂等+部分失败报告；cancel 幂等停阻塞 wait+忽略迟到哨兵；台账原子写+清理+TTL+写失败降级；doctor 检 stale/invalid/dup+resume。
扩展性：--custom（过校验）；三模式；多 machine；agent-kind 无关；保留字过滤覆盖全命令面。
易用性：无参=帮助+roster；name 必填+--suggest；短别名；错误带下一步；mutating 全 --dry-run；doctor 可执行修复；--progress stderr。

## 13. 安全
不碰 server stop/不主动关 pane；只改 hao- label+显式 target name；restore 默认当前 workspace+adopt 可控；非 hao- 需 --force；跨机器校验 profile 不猜 SSH；不自动点审批（abort blocked 需 --force）；result 限安全临时目录 realpath；wake 固定模板不注入 peer summary。

## 14. 敏感审查（脚本化+具体政策）
test_names.py **只断言可判定集合**：完整性+显式 deny+保留字（覆盖**当前完整命令面**）。对外口径=“无显式 deny 词+无保留字”，**不声称“无灰色词”全覆盖**。
- 保留字 deny（含 v4 命令）：wait done list read test agent name ask clear doctor suggest status export import restore pane idle working blocked unknown hat hao herdr task token scope label role machine session tab workspace terminal send prompt focus split close attach config input layout move resize server start swap update open report view **watch cancel abort say result**。
- 灰色 deny：宗教/神秘 corona coven chapel censer bless karma creed faith oath angel spirit grace mercy pardon lamb dove revere saint fairy genie magic spell；暴力 combat bruise attack harm hurt abuse evil vice cull clash claw crack cringe crook crush；身体 diet beard brawn；族群/语言 greek roman latin kanji hanzi pinyin hangul kana hira hebrew arabic cyril thai hindi urdu farsi tamil telugu zulu maori。
- **allow-list（documented）**：文学/叙事 myth saga fable tale verse prose story lyric sonnet rhyme stanza；自然/动物/工具/颜色/材质/食物中性词；**伦理域抽象词 blame shame misuse harden cynic opaque curb brake**（归入 allow，理由：伦理/抽象概念非 occult/暴力/族群）。
- round-4：watch→rook（新命令保留字）。数据完整性 40×40=1600 唯一全 4–6 小写无保留字无显式灰色（脚本断言）。round-1 表标历史勿用于重建。

## 15. 验收（逐模式）
单元 stub+集成 named session（真实 split/label/start/restore/ask/wait/cancel/abort，echo+TUI 缩进正例）。
1. name w2:p9 hawk --scope api→hawk+hao-hawk-api
2. 别名 start temp 重开→restore adopt 改回 hawk；--no-adopt 跳过
3. label=yaml 不被 restore 碰
4. 两 hao-hawk→都歧义 exit6 不 rename；--pick 只恢复被选
5. hao-hawk-api/hao-hawk-web→name hawk 冲突 exit6
6. 另一 workspace 有 live hawk→本 workspace restore/name exit6
7. 预置哨兵/prompt 回显 wait 不成功；真实 agent 最终消息（TUI 缩进/⏺）命中；**Bash tool hao done→wait 看不到（已知限制）**
8. machine fixture：list 两 shape/unknown/remote down/machine+session；本机无 profile 标注
9. suggest 3–5 中英文 task；live 重名扫 names+labels+stale
10. cancel 停阻塞 wait exit10+幂等+迟到哨兵忽略+done-after-cancel 拒绝；abort blocked 需 --force；超时 exit4 带状态尾部；blocked exit5
11. **lifecycle：提交后未观察到 working 不算完成（防假完成）**
12. **file：partial file 不提前返回（原子写/完成标记）；result 路径穿越被拒**
13. **wake 固定模板不含 summary；caller blocked wake best-effort 丢失**
14. **台账：0700/0600、原子写、完成/取消清理、TTL/doctor stale、写失败降级**
15. test_names：完整性+保留字（全命令面）+显式 deny

## 16. 词表（40×40，round-4 后）
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
| 19 | 发布运维 | 信标/港湾/航行/信号 | `beacon` `harbor` `anchor` `helm` `pulse` `signal` `rook` `port` `dock` `gate` `tower` `keep` `ferry` `orbit` `comet` `cameo` `radar` `sonar` `buoy` `canal` `ship` `revert` `moth` `bump` `repo` `binary` `dist` `prod` `sanity` `undo` `redo` `freeze` `thaw` `flag` `health` `vendor` `roll` `stable` `latest` `pinned` |
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
<details><summary>round-1（历史，勿用于重建）</summary>

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

<details><summary>round-2（40）</summary>

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

<details><summary>round-3（25）</summary>

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

<details><summary>round-4（1）</summary>

| 原 | 新 |
|---|---|
| `watch` | `rook` |

</details>

## 18. 实测记录
- r1：forge 14m52s 复现哨兵回显误命中。r2：forge 9m29s，编排者 ^HAO_DONE 等真实完成行超时（TUI 缩进 false-negative）→v3 改 --match。r3：forge 7m4s，**--match 完整 token 命中最终消息行（修复成立）**；forge 实测 Bash tool stdout 不进 pane snapshot→canonical 改最终消息打印。
- agent wait 长任务超时→异步 ask+唤醒+短超时轮询。w2:t1:p9 vs w2:p9→归一化。agent get <label>→not_found→先解析。
- forge 核实：herdr 0.9.5 命令面正确；pane list 含 label/agent list 含 name/status/pane_id 可 join；session.json/snapshots/log 存 label；词表完整性通过；agent name live 唯一/start NAME 必填/rename 有 agent_name_taken；wait-output --regex ^ 按行匹配。
