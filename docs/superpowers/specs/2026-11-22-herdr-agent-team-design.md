# herdr-agent-team 设计稿

> 状态：待用户审阅 · 日期：2026-11-22 · 分支：docs/herdr-agent-team-design

## 1. 背景与痛点

在 herdr 多 agent 协作中有三个痛点：

1. **agent 间等待不顺畅**：`herdr agent wait` / `agent prompt --wait` 只看生命周期状态（idle/done/blocked），不是任务级完成信号；跨机器（`--machine`）场景更难协调。
2. **agent name / pane label 不持久**：herdr 文档明确 agent name 在 agent 退出/被替换时清除；server/客户端重启后 live 状态丢失。
3. **取名难**：要短、有意义、贴合分工，每次现想很费神。

## 2. 已确认的设计决定

| 维度 | 决定 |
|---|---|
| 跨机器拓扑 | 已配置 `herdr machine` profile，封装 `--machine <label>` |
| 持久化范围 | server/客户端重启 + agent 退出后重开 |
| 持久化载体 | **零注册表**：用 `hat-` 前缀的 pane label 作为唯一持久化状态（herdr 的 session.json 会保存 pane label） |
| 命名风格 | 优雅代号（非岗位动词），4–6 位纯小写字母 |
| agent name vs pane label | agent name = 代号；pane label = `hat-<代号>[-<scope>]` |
| 等待机制 | 哨兵 token + `hat` 脚本封装（`pane wait-output --match`） |
| 自动恢复时机 | 仅在 skill 入口跑 `hat restore`，不装 hook、不跑 daemon |
| skill 名 | `herdr-agent-team`，CLI 名 `hat` |
| 词表规模 | 40 组 × 40 个 = 1600 个名字，全部通过敏感内容审查 |

## 3. 目录结构

```
herdr-agent-team/
├── SKILL.md                 # 何时用、三条工作流、入口先跑 hat restore
├── scripts/hat              # Python 3 单文件 CLI，stdlib only
├── references/
│   ├── names.md             # 1600 个名字 + 含义 + 分组（hat suggest 读取）
│   ├── protocol.md          # 哨兵协议、跨机器、失败处理
│   └── restore.md           # label 解析与匹配算法
└── tests/test_hat.py        # 用假 herdr stub 跑单元测试
```

`hat` 无状态：不写 registry、不写 tasks 文件。唯一持久化是 herdr 自己的 pane label。

## 4. 命名模型

- **agent name**：从词表选一个代号，`^[a-z]{4,6}$`
- **pane label**：`hat-<name>` 或 `hat-<name>-<scope>`，scope 为小写字母/数字/连字符，≤12
- `hat restore` 只处理匹配 `^hat-([a-z]{4,6})(?:-([a-z0-9][a-z0-9._-]{0,12}))?$` 的 label，其他 label（如 `yaml`、`atcl`）完全不碰
- 名字冲突：同组内换下一个候选，不加数字（保持纯字母）
- `--custom <name>` 允许表外名，仍强制 4–6 位小写字母
- 分组只用于选名提示，不写进 label

## 5. 命令面

| 命令 | 作用 |
|---|---|
| `hat name <target> <name> [--scope api]` | agent 改名 + pane label 设为 `hat-<name>[-scope]` |
| `hat restore [--machine M] [--dry-run]` | 扫 live pane label，给对应 agent 补名字 |
| `hat ask <target> "<task>" [--wait] [--timeout 10m] [--machine M]` | 发任务 + 哨兵；`--wait` 内联等待 |
| `hat wait <target> --token T [--timeout 10m] [--machine M]` | 等哨兵出现 |
| `hat done --token T [--summary "..."]` | 对端打完成标记 |
| `hat list [--machine M]` | 列出 `hat-` 标签、对应 agent 名、live 状态 |
| `hat suggest "<task>" [--scope api]` | 按关键词选组，返回 3 个未占用候选 |
| `hat clear <target>` | 清 agent 名和 hat label |
| `hat doctor [--machine M]` | 检查 HERDR_ENV、machine profile、label 规范 |

退出码：`0` 成功、`2` 用法、`3` target 不存在、`4` 超时、`5` blocked、`6` 角色冲突、`7` machine/profile 不可用。

## 6. restore 算法

1. 读 panes（本地或 `--machine`），筛出 `hat-` label
2. 解析 role/scope；取该 pane 当前 agent（`agent list` 按 pane_id 关联）
3. 若 agent 名 ≠ role：`herdr agent rename <pane> <role>`
4. 同一 role 出现在多个 pane（label 重复）：按 pane_id 排序只恢复第一个，其余报冲突（退出码 6），不加数字后缀，保持纯字母规则
5. 只有 shell、没有 agent 的 pane：跳过；等 agent 起来后再跑 restore
6. `--dry-run` 只输出将执行的 rename

## 7. 等待协议（哨兵）

`hat ask` 生成 token `hat-<8hex>`，prompt 末尾附：

```
[TASK hat-1a2b3c4d]
<task>

When finished, print exactly this last line:
HERDR_DONE hat-1a2b3c4d
```

- `--wait`：`herdr [--machine M] pane wait-output <pane> --match "HERDR_DONE <token>" --timeout <ms>`，命中后返回最后 40 行
- 超时：返回 `agent get` 状态 + 最后 40 行
- `pane wait-output` 不可用时回退为每 2 秒 `agent read` 轮询
- `agent prompt` 返回 `agent_blocked` 时立即停止并报告，绝不自动点掉审批
- 所有 herdr 调用统一加 `--machine`；拒绝 `--machine` 与 `--current` 组合
- token 不落盘；异步时 `hat ask` 打印 token 和下一步 `hat wait` 命令

## 8. 错误与安全

- 不碰 `herdr server stop`、不主动关 pane
- 只改 `hat-` 标签和显式 target 的 agent 名
- 跨机器先校验 `herdr machine list --json` 里有该 label；没有就提示 `herdr machine add`，不猜 SSH host
- 限制：如果 herdr 某次升级把 pane label 也丢了，hat 无法恢复（零注册表的代价）；`hat doctor` 会提示

## 9. 敏感内容审查

对 1600 个名字做了政治/宗教/数据/暴力/种族/金融六类审查，**242 个高/中风险名已全部替换**为 curated 安全词（自然/天体/工具/抽象/动物/颜色/材质/食物类）。替换后仍满足：全部 `^[a-z]{4,6}$`、全局唯一、每组 40 个。

低风险保留（道德哲学/防御类中性词）：`right` `just` `equal` `same` `aegis` `ethos` `ethic` `moral` `virtue` `wisdom` `truth` `honest` `candor` `sentry` `moat` `guard` `shield` `ward` `vigil` `patrol` `scout` `ranger`。

## 10. 验收

1. `hat name reviewer --scope api` → agent `reviewer` + label `hat-reviewer-api`
2. agent 退出后重开 → `hat restore` 从 label 恢复 `reviewer`
3. label 为 `yaml` 的 pane 不被 restore 触碰
4. 两个 pane 都标 `hat-reviewer` → 只恢复第一个为 `reviewer`，第二个报冲突（退出码 6），不产生 `reviewer2`
5. `hat ask --wait` 命中哨兵返回；超时路径带状态与尾部输出
6. `--machine` 命令拼装用 stub 验证；无 profile 时报错
7. `hat suggest` 避开 live 重名

## 11. 名字词表（40 组 × 40）

以下为敏感审查替换后的最终词表。`hat suggest` 按任务关键词选组，返回该组 3 个未占用候选。

| # | 分工 | 主题 | 40 个候选名 |
|---|---|---|---|
| 1 | 规划编排 | 地图/方向/星光/秩序 | `atlas` `north` `lumen` `vega` `orion` `polar` `lyra` `aegis` `ethos` `prime` `alba` `alto` `amber` `axis` `order` `logic` `arch` `amble` `nova` `aurora` `vision` `intent` `arbor` `ardor` `vista` `rudder` `tack` `spire` `apex` `summit` `zenith` `peak` `crest` `cycle` `phase` `stage` `step` `scheme` `tactic` `method` |
| 2 | 需求产品 | 价值/用户/市场/目标 | `value` `worth` `scope` `brief` `pitch` `angle` `focus` `demand` `offer` `solve` `case` `aria` `listen` `market` `growth` `trend` `goal` `core` `first` `seed` `need` `want` `wish` `must` `armor` `aroma` `aspen` `survey` `niche` `epic` `task` `ticket` `beta` `pilot` `launch` `deck` `deal` `query` `agile` `sprint` |
| 3 | 用户研究 | 观察/倾听/行为/群体 | `study` `learn` `sense` `feel` `mood` `quote` `heat` `funnel` `drop` `churn` `retain` `habit` `aura` `cohort` `panel` `poll` `group` `circle` `avian` `azure` `field` `shadow` `notice` `read` `talk` `chat` `reply` `depth` `broad` `narrow` `babel` `bail` `spot` `bale` `bark` `barn` `baron` `basil` `basin` `mind` |
| 4 | 架构接口 | 结构/边界/契约/骨架 | `frame` `shell` `layer` `bayou` `proto` `module` `plugin` `spine` `base` `form` `shape` `span` `dome` `vault` `keel` `mast` `pillar` `column` `scale` `plane` `beam` `girder` `joist` `rafter` `lintel` `corbel` `plinth` `atrium` `facade` `link` `schema` `driver` `model` `object` `entity` `bean` `tree` `heap` `list` `trie` |
| 5 | 设计体验 | 色彩/形态/笔触/韵律 | `muse` `iris` `opal` `forma` `motif` `verve` `poise` `glint` `bloom` `tint` `tone` `shade` `brush` `easel` `craft` `sculpt` `chisel` `etude` `lyric` `sonnet` `draft` `wire` `layout` `space` `align` `margin` `border` `radius` `ombre` `glow` `matte` `glass` `frost` `noise` `grain` `stripe` `color` `chroma` `swatch` `icon` |
| 6 | 视觉品牌 | 标识/排版/质感/风格 | `brand` `logo` `mark` `emblem` `badge` `sigil` `banner` `poster` `flyer` `cover` `spread` `type` `serif` `sans` `font` `weight` `italic` `bold` `light` `heavy` `gothic` `rhythm` `photo` `crop` `blur` `sharp` `beard` `filter` `gloss` `satin` `linen` `paper` `paint` `stroke` `beast` `deco` `retro` `modern` `clean` `subtle` |
| 7 | 前端体验 | 交互/动效/组件/界面 | `cursor` `click` `touch` `swipe` `motion` `anim` `ease` `flow` `fluid` `smooth` `crisp` `clear` `glide` `slide` `shift` `hover` `canvas` `sketch` `menu` `theme` `render` `reflow` `bundle` `chunk` `beech` `fetch` `state` `store` `props` `hook` `input` `toggle` `slider` `picker` `modal` `toast` `card` `drawer` `sheet` `dialog` |
| 8 | 后端服务 | 服务/队列/协议/并发 | `serve` `route` `queue` `beetle` `cron` `beige` `socket` `stream` `buffer` `pipe` `broker` `router` `server` `engine` `retry` `batch` `async` `event` `shard` `raft` `topic` `pubsub` `fanout` `rest` `grpc` `soap` `http` `cookie` `header` `body` `status` `code` `view` `join` `berry` `offset` `commit` `bevel` `lease` `atomic` |
| 9 | 移动桌面 | 触控/设备/离线/同步 | `mobile` `birch` `hybrid` `tablet` `bison` `wear` `haptic` `vibe` `shake` `tilt` `rotate` `orient` `screen` `pane` `tray` `widget` `hotkey` `pull` `stash` `online` `sync` `local` `remote` `push` `notify` `power` `drain` `sleep` `wake` `resume` `pause` `play` `retina` `inset` `notch` `keypad` `share` `send` `blade` `start` |
| 10 | 实现构建 | 锻造/金属/结构/火 | `forge` `flint` `ember` `anvil` `cedar` `kiln` `steel` `iron` `bolt` `gear` `lever` `pylon` `truss` `brick` `mortar` `weld` `solder` `alloy` `smelt` `hearth` `cast` `mold` `mint` `carve` `lathe` `mill` `blaze` `clamp` `vise` `file` `rasp` `bleak` `wrench` `pliers` `ruler` `tape` `glue` `epoxy` `resin` `clay` |
| 11 | 数据工程 | 管道/存储/格式/血缘 | `ingest` `dedupe` `enrich` `merge` `split` `arrow` `avro` `json` `yaml` `lake` `pond` `mart` `cube` `fact` `star` `snow` `origin` `source` `target` `sink` `spigot` `faucet` `valve` `null` `blank` `empty` `dupe` `stale` `fresh` `late` `drift` `skew` `sched` `bless` `backup` `save` `loader` `parser` `mapper` `sorter` |
| 12 | 数据科学 | 统计/推断/图表/概率 | `stats` `blimp` `median` `range` `quart` `season` `factor` `latent` `label` `train` `score` `rank` `topk` `report` `infer` `causal` `effect` `impact` `lift` `uplift` `pivot` `slice` `dice` `rollup` `plot` `legend` `tick` `bins` `blitz` `bluff` `prior` `bayes` `markov` `blurb` `blush` `random` `resid` `ridge` `lasso` `gini` |
| 13 | 机器学习 | 模型/训练/推理/神经 | `neuron` `neural` `boat` `epoch` `embed` `prompt` `window` `agent` `reward` `action` `head` `norm` `relu` `tanh` `gelu` `lstm` `unet` `lora` `qlora` `peft` `rlhf` `search` `grad` `bobbin` `warmup` `prune` `sparse` `dense` `tune` `steer` `logit` `spike` `micro` `macro` `fold` `expert` `small` `large` `tiny` `giant` |
| 14 | 测试实验 | 试验/基准/模糊/金丝雀 | `trial` `sample` `bench` `bough` `assert` `expect` `bourn` `stub` `suite` `golden` `bower` `canary` `chaos` `stress` `load` `surge` `burst` `quota` `metric` `grade` `test` `verify` `plan` `setup` `before` `after` `unit` `brace` `brass` `brave` `happy` `corner` `flaky` `line` `branch` `soak` `perf` `blue` `green` `check` |
| 15 | 调试修复 | 追踪/探针/疗愈/修补 | `hound` `trace` `probe` `spark` `rivet` `mend` `heal` `cure` `balm` `salve` `suture` `splint` `remedy` `tinker` `patch` `clue` `trail` `track` `brawn` `ferret` `bisect` `repro` `bread` `breeze` `brew` `warn` `root` `cause` `reason` `hotfix` `reduce` `shrink` `attach` `briar` `brim` `brine` `brisk` `brook` `loop` `broom` |
| 16 | 验证审阅 | 锐眼/量具/证明/守卫 | `hawk` `lens` `prism` `ward` `proof` `verity` `broth` `edge` `sift` `trust` `gauge` `plumb` `level` `square` `assay` `valid` `scan` `sweep` `shield` `lynx` `glance` `peer` `skim` `bruise` `bubble` `spec` `canon` `stamp` `pass` `buckle` `veto` `assent` `ruling` `appeal` `patrol` `scout` `ranger` `vigil` `look` `rule` |
| 17 | 安全隐私 | 锁/密钥/防护/威胁 | `guard` `lock` `crypt` `buff` `bulb` `permit` `policy` `safe` `secure` `seal` `sign` `auth` `login` `access` `grant` `deny` `threat` `bumper` `sentry` `moat` `hash` `salt` `nonce` `hmac` `vuln` `bunch` `burl` `bush` `bustle` `butte` `button` `cabin` `zero` `least` `purple` `cactus` `cadet` `cage` `cairn` `cake` |
| 18 | 基础设施 | 云/网络/存储/平台 | `cloud` `infra` `deploy` `subnet` `switch` `tunnel` `egress` `packet` `swarm` `hive` `host` `image` `volume` `disk` `mount` `blob` `bucket` `pool` `mirror` `memory` `hyper` `calf` `metal` `chip` `board` `fabric` `vlan` `vxlan` `dhcp` `ipam` `cidr` `ospf` `mpls` `callus` `resize` `init` `config` `param` `cert` `jump` |
| 19 | 发布运维 | 信标/港湾/航行/信号 | `beacon` `harbor` `anchor` `helm` `pulse` `signal` `watch` `port` `dock` `gate` `tower` `keep` `ferry` `orbit` `comet` `cameo` `radar` `sonar` `buoy` `canal` `ship` `revert` `swap` `bump` `repo` `binary` `dist` `prod` `sanity` `undo` `redo` `freeze` `thaw` `flag` `health` `vendor` `roll` `stable` `latest` `pinned` |
| 20 | 监控成本 | 告警/预算/计量/节俭 | `candle` `canoe` `canopy` `canyon` `cape` `limit` `rate` `util` `usage` `caper` `carol` `cask` `castle` `cater` `stat` `tally` `count` `idle` `thrift` `frugal` `dash` `uptime` `floor` `cavern` `ceil` `cellar` `cement` `censer` `chafe` `chaff` `spare` `oncall` `pager` `chair` `rota` `quiet` `silent` `chalk` `chant` `chapel` |
| 21 | 网络通信 | 协议/信号/传输/连接 | `https` `smtp` `imap` `sftp` `mqtt` `amqp` `coap` `quic` `radio` `wave` `fiber` `coax` `cable` `ping` `pong` `call` `dial` `ring` `beep` `buzz` `feed` `cell` `slot` `band` `modem` `codec` `demux` `parley` `chirp` `squawk` `shout` `speak` `flare` `uplink` `roam` `tether` `pair` `bond` `hail` `blink` |
| 22 | 存储检索 | 索引/结构/容器/查找 | `folder` `seek` `find` `lookup` `match` `sort` `btree` `mvcc` `chase` `crdt` `paxos` `chasm` `mmap` `cold` `warm` `tier` `hnsw` `chaste` `radix` `octree` `extent` `inode` `dentry` `vacuum` `parse` `format` `cheek` `fifo` `lifo` `pack` `shelf` `rack` `locker` `chest` `crate` `pallet` `carton` `desk` `closet` `spool` |
| 23 | 研究检索 | 智慧/索引/解密/探索 | `sage` `index` `cipher` `quest` `raven` `wren` `lark` `finch` `heron` `swift` `robin` `magpie` `merlin` `cheese` `rune` `lore` `riddle` `enigma` `lexis` `path` `browse` `chef` `delve` `scent` `eagle` `falcon` `osprey` `condor` `kite` `stork` `ibis` `egret` `swan` `goose` `teal` `cherry` `gull` `tern` `puffin` `petrel` |
| 24 | 文档表达 | 书写/诗行/故事/清晰 | `quill` `verse` `fable` `glyph` `tome` `prose` `story` `voice` `echo` `page` `leaf` `scroll` `rhyme` `stanza` `meter` `chess` `phrase` `syntax` `lucid` `memo` `write` `edit` `copy` `paste` `clip` `note` `digest` `title` `style` `term` `jargon` `slang` `cite` `claim` `essay` `blog` `post` `book` `issue` `figure` |
| 25 | 本地化翻译 | 语言/文字/区域/文化 | `locale` `lingua` `verb` `noun` `script` `kanji` `hanzi` `pinyin` `latin` `greek` `roman` `choir` `chorus` `chrome` `text` `word` `clause` `idiom` `tongue` `globe` `global` `region` `zone` `area` `custom` `chuck` `chum` `char` `ascii` `hangul` `kana` `hira` `cider` `cigar` `cinder` `cinema` `circus` `citrus` `city` `clam` |
| 26 | 合规治理 | 议事/契约/裁决/秩序 | `nexus` `envoy` `herald` `relay` `clang` `bridge` `warden` `keeper` `forum` `agora` `quorum` `proxy` `accord` `truce` `pact` `clap` `civic` `polis` `realm` `clash` `ethic` `moral` `clasp` `claw` `cleat` `cleft` `clever` `cliff` `diet` `house` `cling` `cloak` `clod` `clog` `peace` `cloth` `clover` `honor` `equity` `fair` |
| 27 | 法务风控 | 法律/合同/风险/保险 | `clown` `clump` `terms` `breach` `waiver` `patent` `docket` `hedge` `damage` `clutch` `coast` `coat` `cobalt` `export` `import` `will` `estate` `heir` `settle` `defend` `accuse` `plead` `cobble` `alibi` `motive` `notary` `clerk` `scribe` `assure` `insure` `surety` `cobra` `cocoa` `coil` `liable` `caveat` `umpire` `deed` `lien` `escrow` |
| 28 | 教学讲解 | 导师/课程/练习/启发 | `tutor` `mentor` `coach` `guide` `lesson` `course` `class` `quiz` `exam` `hint` `demo` `show` `tell` `wonder` `answer` `simple` `plain` `skill` `repeat` `recall` `teach` `myth` `tale` `saga` `school` `campus` `studio` `ponder` `think` `recap` `flash` `praise` `tweak` `easy` `hard` `vivid` `cola` `novice` `collar` `mentee` |
| 29 | 支持成功 | 帮助/关怀/响应/忠诚 | `help` `care` `assist` `rescue` `smile` `kind` `nice` `calm` `soothe` `triage` `assign` `refer` `loyal` `greet` `colon` `colt` `comb` `thread` `video` `glad` `cheer` `sorry` `combat` `comic` `comma` `conch` `cone` `manual` `howto` `please` `update` `inform` `advise` `portal` `center` `heart` `hope` `confer` `hand` `conga` |
| 30 | 销售市场 | 交易/推广/渠道/激励 | `sell` `sale` `close` `lead` `promo` `social` `viral` `hype` `news` `press` `asset` `media` `free` `resell` `distro` `reach` `coupon` `upsell` `cart` `basket` `shop` `retail` `bazaar` `mall` `booth` `stand` `engage` `tend` `site` `maker` `champ` `bounty` `bonus` `gift` `prize` `award` `medal` `points` `outlet` `kiosk` |
| 31 | 内容社交 | 媒体/社区/互动/创作 | `vlog` `reel` `short` `live` `like` `follow` `handle` `emoji` `upvote` `karma` `club` `guild` `team` `crew` `squad` `cook` `cool` `scene` `beat` `tempo` `chord` `melody` `song` `audio` `zine` `onair` `meet` `meetup` `camp` `gather` `cope` `game` `arcade` `puzzle` `trivia` `kudos` `tile` `flair` `about` `mosaic` |
| 32 | 财务计费 | 货币/账务/薪酬/投资 | `copper` `cord` `cork` `corn` `cornet` `corona` `corpus` `corral` `corset` `entry` `annual` `month` `week` `paid` `gross` `cortex` `cosmic` `cosmos` `cotton` `couch` `county` `couple` `cousin` `cove` `coven` `covet` `cozy` `crab` `crack` `cradle` `cram` `crank` `crater` `crave` `crayon` `craze` `cream` `create` `creek` `creep` |
| 33 | 人力招聘 | 人才/职业/团队/流动 | `talent` `hire` `staff` `career` `ladder` `role` `review` `rubric` `folio` `buddy` `morale` `perk` `values` `office` `seat` `room` `apply` `intern` `junior` `senior` `crib` `cringe` `ally` `croak` `crock` `crocus` `crook` `leave` `break` `repose` `roster` `swing` `flex` `temp` `perm` `cross` `crouch` `nest` `roost` `burrow` |
| 34 | 项目管理 | 进度/看板/节奏/交付 | `scrum` `wrap` `gantt` `todo` `done` `doing` `crow` `time` `date` `work` `urgent` `major` `minor` `point` `size` `agenda` `item` `lane` `swim` `slack` `float` `fast` `slow` `speed` `pace` `weekly` `daily` `clock` `timer` `bell` `remind` `next` `last` `kick` `begin` `open` `ready` `park` `hold` `wait` |
| 35 | 采购供应链 | 物流/仓储/运输/交易 | `supply` `tender` `cargo` `depot` `yard` `quay` `berth` `crane` `fork` `hoist` `chute` `belt` `roller` `seller` `crude` `trader` `cruise` `haggle` `bulk` `sack` `tote` `skid` `truck` `rail` `crumb` `safety` `pick` `haul` `unload` `crunch` `robot` `convey` `lading` `tanker` `barge` `vessel` `crush` `drum` `pier` `wharf` |
| 36 | 生态合作 | 连接/共生/联盟/共享 | `place` `crust` `addon` `biome` `mutual` `coop` `cuddle` `cuff` `invest` `spoke` `axle` `door` `give` `trade` `barter` `lend` `borrow` `cumin` `cupola` `grove` `forest` `reef` `coral` `kelp` `moss` `fern` `vine` `shoal` `curd` `knot` `weave` `braid` `strand` `curfew` `shared` `common` `cohost` `clone` `curate` `merit` |
| 37 | 战略分析 | 框架/决策/竞争/格局 | `swot` `pest` `porter` `five` `curl` `chain` `life` `choice` `thesis` `assume` `lean` `wedge` `ocean` `weak` `assess` `turn` `move` `stake` `return` `yield` `bull` `bear` `lion` `tiger` `shark` `curry` `beach` `stance` `codex` `firm` `curt` `land` `cute` `wolf` `orca` `arena` `turf` `sector` `domain` `basis` |
| 38 | 创意灵感 | 想象/新奇/玩心/火花 | `idea` `dream` `cymbal` `whim` `fancy` `novel` `unique` `rare` `weird` `wild` `dare` `draw` `doodle` `mash` `blend` `remix` `twist` `flip` `bend` `fairy` `genie` `magic` `spell` `charm` `joke` `quip` `jest` `jolly` `merry` `zest` `bang` `boom` `fizz` `zing` `neon` `improv` `adlib` `riff` `solo` `encore` |
| 39 | 伦理安全 | 伤害/美德/诚实/守护 | `cynic` `acorn` `alder` `misuse` `aloe` `harden` `virtue` `aster` `good` `bamboo` `truth` `honest` `candor` `opaque` `curb` `brake` `right` `wisdom` `aware` `attune` `heed` `just` `equal` `same` `candid` `frank` `cred` `brier` `dahlia` `gentle` `still` `meek` `humble` `modest` `daisy` `blame` `shame` `regard` `esteem` `ebony` |
| 40 | 领域专家 | 医学/科学/工程/艺术 | `medic` `vital` `juris` `earth` `chem` `astro` `math` `clinic` `pharma` `elder` `flora` `neuro` `cardio` `derma` `onco` `renal` `immune` `garden` `hazel` `heath` `holly` `laurel` `nurse` `doctor` `econ` `devops` `lilac` `mecha` `aero` `auto` `civil` `struct` `mechan` `elect` `optic` `editor` `music` `visual` `film` `dance` |

## 12. 替换映射（风险名 → 安全名）

<details><summary>展开 242 条替换</summary>

| 原（风险） | 新（安全） |
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
