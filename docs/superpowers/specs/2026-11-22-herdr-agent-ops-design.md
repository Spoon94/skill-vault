# herdr-agent-ops 设计稿 v6

> 待 forge 复审 → 用户授权 · 2026-11-22 · 分支 docs/herdr-agent-team-design
> v6：收口 round-5 七条——台账 tombstone 保 result_path、--wake 限同机+主 fallback 宿主 scheduler、lifecycle 自实现门槛可 cancel、匹配器改 server 侧容忍正则为主（无单调游标）、邻接容忍标点/边框、abort 用户级授权（TTY/0600 approval）、TTL 按 updated 不清 running、status/say 行为补全。

## 1. 背景
herdr 多 agent：任务级等待缺失、名字不持久、取名难。

## 2. 命名与调用
skill herdr-agent-ops；CLI hao；label 前缀 hao-。调用 ${CLAUDE_SKILL_DIR}/scripts/hao 或 PATH；远端无 python3/hao 退化手动打印。doctor 查 python3≥3.9/herdr/HERDR_ENV/machine/resume/XDG 默认。--json+人读；--progress/日志 stderr；**hao done 例外：哨兵 stdout 最后一行、JSON stderr（写进 protocol.md schema）**。短别名无歧义：n=name r=restore a=ask w=wait d=done l=list s=suggest c=clear st=status sy=say rs=result；doctor/cancel/abort 无别名。

## 3. 关键决定
- 名字映射零注册表：hao- label 唯一名字载体（session.json 存 label；agent_name/resume best-effort 非契约）。
- 任务协调用可清理临时台账（非名字注册表）：$XDG_STATE_HOME/hao/tasks/<shortid>.json，默认 ~/.local/state/hao/tasks（XDG 未设必须实现），目录 0700 文件 0600，绝对路径+realpath。字段：token/shortid(12hex,创建前查重)/target/machine/caller/mode/status/created/**updated**/result_path/submit_state/submit_seq。waiter_pid 仅展示不 kill。原子写 temp+rename+per-shortid 锁。
- **tombstone**：完成/取消不立即删台账，转 status=done/cancelled 的 tombstone **保留 result_path**，供 hao result 按 shortid 读取；result 读取后或 TTL 到期才删。**TTL 按 updated/heartbeat 判 stale，只清 terminal/stale，不清 running**（>24h running 有误清风险→用 updated+waiter 状态）。doctor 清 stale tombstone。写失败降级：ask 继续发送但禁 wake/cancel 并警告（--strict-ledger 报错）。token 落盘（非秘密，诚实）。
- 命名 ^[a-z]{4,6}$ per-machine 唯一；一代号一 agent；scope 仅 label 注解。等待默认 sentinel，canonical=最终 assistant 消息打印哨兵。长等待 ask 异步+唤醒；终止 cancel/abort。恢复仅 skill 入口不装 hook。跨机器本机无 profile 仅 stub。

## 4. 目录
herdr-agent-ops/{SKILL.md,scripts/hao,references/{names,protocol,restore}.md,tests/{test_hao,test_names}.py+integration/}。自定义仅 --custom（过校验）。

## 5. Target 解析
hao-→label；w<N>:p<M>→pane id（兼容 w:t:p 归一化）；其他→live name。唯一 pane；零匹配 exit3 多匹配 exit6 需 --pick。目标机器解析；ask 回显稳定 target。pane id 可含字母，move 后用新 id/label。

## 6. 命名模型
name ^[a-z]{4,6}$ per-machine 唯一；label ^hao-([a-z]{4,6})(?:-([a-z0-9][a-z0-9-]{0,11}))?$，scope 1–12 小写/数字/连字符，label≤23。一代号一 agent；name 预检整台 machine 所有 live names+所有 workspace label role+stale，冲突 exit6。name 必填（非 TTY），--suggest 自动选一并打印。shell-only 只设 label；非 hao- 需 --force。先 label 后 name，rename 失败留 label 交 restore。clear 先 label 后 name；不动非 hao-（除非 --force）；doctor 提示残留 name。

## 7. restore
口径：session.json 存 label+agent_name；resume=true 恢复受支持 agent；label 解耦槽位。兜底：退出/被替换/unsupported/resume=false/失败。
1. scope 只决定恢复哪些 label（默认当前 workspace，--workspace/--all）。2. name 占用扫整台 machine，跨 workspace 同名 exit6。3. pre-flight 检测冲突/占用/startup pending/stale/非法。4. 不自动选 winner：同 role 多 pane 全歧义 exit6+候选，--pick 只恢复被选者。5. 默认 adopt：非空不等价 name 改 role；--no-adopt 只填无名；--dry-run；非 hao- 需 --force。6. 幂等+部分失败报告；startup pending 等待/重试/报告。doctor 列 stale/invalid/dup+resume；repurpose 前先 clear；restart 测试隔离 named session。list/doctor 默认当前 workspace（--all 扩大），输出显式 machine/workspace/tab/pane/cwd/agent，name 唯一性 per-machine 标注不误导。

## 8. 等待协议
### 8.1 canonical 完成 + 匹配器（server 侧容忍正则为主，无单调游标）
- canonical=peer 最终 assistant 消息最后一行打印 HAO_DONE <token>。Bash tool stdout 不进 pane snapshot（forge 实测），hao done 经 tool 执行 stdout 不可靠，但 **hao done 的台账/wake 副作用仍可用**（见 8.3）。
- token=hao-<12–16hex>；task marker 短 id [TASK <shortid>] 不含完整 token；prompt 拆 token 两段令 peer 拼接；ask 扫描整个最终 prompt 含完整 token 则拒绝/改写。
- **主检测=server 侧 pane wait-output --regex 容忍正则**（短超时循环兼顾 cancel）：`^\s*(?:[⏺●✻│⎿]\s*)?HAO_DONE\s+<token>[\s.。!！│]*$`。要求 HAO_DONE 与 token 邻接→**token-only 引用（reasoning/tool-call 源码）不匹配，天然无 busy-loop**；容忍 TUI 缩进/⏺ 前缀/尾部标点/代码框边框。**不依赖 pane read 单调游标**（pane read 无 offset/绝对行号，滚动窗口第 0 行会变，不能当单调游标）。
- 命中后校验：同一 matched_line 含 HAO_DONE+完整 token（允许尾部 [.。!！] 与边框 │）、位于快照尾部 N=40 行；否则视为无效命中→改用 pane read 后缀重叠（上次窗口尾 K 行与新窗口对齐）推进越过该行，不 re-arm 同一匹配。
- **滚动丢失 fallback**：sentinel 可能被大量输出顶出窗口；超时后 pane read --lines 大窗口重扫该正则；仍无→继续短轮询或 exit4。--match 完整 token 仅作可选 wakeup 预筛，每轮新行无条件跑邻接判定；预筛 miss 也 fallback 扫全窗口。
- baseline 旧 token 预检：生成 token→读快照确认不存在否则重生成；发拆分 prompt；可选等 [TASK shortid] 再确认 token 不存在；命中若属发送前快照旧 token→exit9 不循环。
### 8.2 等待模式
- sentinel（默认核心）：上述。
- **lifecycle 同步且可 cancel**：--mode lifecycle 隐含 --wait 拒绝 async。hao ask 用 **agent prompt（不带 --wait）提交**，然后**自实现门槛**：5s 内短轮询 agent get 要求观察到 working/blocked，否则 exit9；之后 **agent wait --timeout 5–10s 循环+每轮查台账**（可被 cancel）。仅单轮、提交时 agent 非 working；已 working 不得把当前 turn 当本任务完成。
- file local-only：ask --mode file 创建 tasks/<shortid>/result.md，result_path 写台账（tombstone 保留）；peer 原子写 temp+rename 或完成标记/长度校验防 partial；hao result <shortid> 用台账 result_path+realpath+防 symlink/穿越，peer 返回其他路径拒绝或需 --file。跨机器 result experimental/不支持。
- metadata 旁路 experimental。不做可插拔框架。
### 8.3 长等待与唤醒
- ask 默认异步立即返回 token+shortid；--wait 内联（lifecycle 强制）。默认超时 30m，--timeout 0 无限；--progress 心跳 stderr。台账 caller-local+machine 键。
- **--wake 生效条件**：仅当 peer 运行 hao done（或等价 completion hook）**且能访问 caller-local 台账（同机）**时，hao done 写台账 status=done 并注入固定模板 [HAO_WAKE] <shortid> <status>（不含 peer summary）到 caller。**最终消息打印哨兵只是 wait 信号，不产生 wake**。跨机器 caller-local 台账不可达→peer 无法 wake，**只能 caller 侧 poll**。
- **主 fallback=宿主 scheduler（ScheduleWakeup）定时复查 hao wait --timeout 短 + caller 侧短轮询**；token 稳定可重复 wait。hao watch experimental（--once/超时/幂等/清理，非隐性 daemon，无验收不承诺）。caller blocked→agent_blocked wake 丢失 best-effort；caller 不存在 exit3。
### 8.4 终止与超时（全模式可 cancel）
- 所有模式短超时轮询+每轮查台账：sentinel 用 wait-output --regex 短循环；lifecycle 用 agent wait --timeout 5–10s 循环；file 文件轮询循环。cancel 停任一阻塞 wait。cancelled exit10（别于 timeout4）。
- cancel <token|shortid> 只标台账 cancelled（幂等不碰 peer）；waiter 停；迟到哨兵忽略；cancel 后 done 不得标 done；token 不存在 exit3。
- abort <token> [--interrupt]：cancel+可选发键 send-keys esc→ctrl+c。**blocked 下 --interrupt 只认用户级授权：TTY 二次确认，或用户拥有的 0600 approval 文件/独立 approval token**；HAO_ABORT_ALLOW=1 仅是“用户预先授权”约定**不是安全边界**（agent 可在自己 shell 设 env，甚至直接 herdr send-keys 绕过 hao）。文档明示：abort 授权是 guardrail 非 security boundary；esc/ctrl+c 可能丢审批。abort blocked 无授权 exit5。不关 pane 不停 server。cancel 与 abort 分开。
- 超时 exit4+状态+尾部→编排者决定重试/cancel/abort；blocked exit5→交用户审批或 abort，绝不自动点审批；exited/closed exit3。一 pane 一 task best-effort（台账 busy 无分布式锁）；无 --queue。
- hao done --token T [--summary]：先 summary 后哨兵 stdout 最后一行；写台账 done+tombstone result_path；同机有 --wake 则注入；stdout 可能不可见但副作用可用；done 不在 pane/无法渲染 exit8；远端无 hao 手动打印（仅 wait 信号）。
- **status** 默认 target=当前 pane（HERDR_PANE_ID），输出 agent 状态/label/mode/outstanding shortid；**say** fire-forget 无哨兵不写台账，对 blocked exit5、对 working best-effort 提交（agent prompt 语义）；**result** 按 shortid 读 tombstone result_path。

## 9. 错误码
0 成功/2 用法（invalid_agent_name·mode 非法·result 路径被拒·别名未知·--file 非法·HAO_ABORT_ALLOW 格式错）/3 target 不存在·exited·closed·result 文件不存在·cancel token 不存在·wake caller 不存在/4 超时/5 blocked·abort blocked 无授权·say 对 blocked/6 冲突·歧义·name taken·say 对 working 拒绝（若严格）/7 machine 不可用/8 herdr·server 错误（prompt_stalled·remote failure·agent_not_ready·agent_pane_not_found·stale_pane_target·invalid_agent_timeout·watch 失败·台账损坏/不可写·done 不在 pane）/9 协议错误（baseline 旧 token·lifecycle 未观察 working 转变）/10 cancelled。startup pending 可重试。解析 herdr JSON error.code/stderr 不透传；mutating 不盲重试。

## 10. 跨机器
本机 machine list=[] 仅 stub 标注未验证。--machine 不与 --session/--remote 组合，不传 --current/本地 ID。name/clear/suggest/list/restore/ask/wait/cancel/abort 支持 --machine，target 远端解析。result 跨机器 experimental/不支持（file local-only；--machine 仅 peer 最终消息已含内容）。**wake 跨机器不支持**（caller-local 台账不可达→caller 侧 poll/宿主 scheduler）。doctor --machine 用 machine status；无/未知 profile exit7。台账 caller-local+machine 键 caller 侧 poll。远端 server 须运行 API 兼容；连接失败≠未发生。

## 11. suggest
每组中英文关键词别名+确定性打分；组耗尽→相邻组/--custom。未占用=per-machine 所有 live names+所有 label role+stale。排除保留字（全命令面）；--suggest 非交互；--json 候选/组/理由；验收 3–5 中英文 task。

## 12. 五维
功能：name/restore/ask/wait/done/list/suggest/clear/doctor/status/say/result/cancel/abort+target 归一化+稳定回显+--json+短别名。延后 broadcast/export-import；去掉可插拔框架/names.local/hook/交互式 input/--queue。watch/metadata/file 跨机器/result 跨机器/wake 跨机器=experimental 无验收不承诺不影响 sentinel 主路径。
性能：server 侧 wait-output --regex/agent wait 短超时轮询（兼顾 cancel）；--lines 限界；restore 单遍 pre-flight；suggest 静态索引；rename 循环非 batch。
容灾：防回显+防 false-negative+容忍正则天然防 busy-loop+旧 token 预检+滚动丢失重扫 fallback；blocked/exited/closed 立即返回；超时给状态尾部；mutating 不盲重试；restore 幂等+部分失败报告；cancel 全模式幂等停阻塞+忽略迟到哨兵；台账原子写+锁+tombstone+TTL 按 updated 不清 running+写失败降级；doctor 检 stale/invalid/dup+resume。
扩展性：--custom（过校验）；三模式；多 machine；agent-kind 无关；保留字过滤覆盖全命令面。
易用性：无参=帮助+roster；name 必填+--suggest；短别名无歧义；错误带下一步；mutating 全 --dry-run；doctor 可执行修复；--progress stderr；list/doctor 显式 scope。

## 13. 安全
不碰 server stop/不主动关 pane；只改 hao- label+显式 target name；restore 默认当前 workspace+adopt 可控；非 hao- 需 --force；跨机器校验 profile 不猜 SSH；不自动点审批（abort blocked 需 TTY/0600 approval，guardrail 非 security boundary）；result 限安全临时目录 realpath；wake 固定模板不注入 summary；不 kill 任意 PID。

## 14. 敏感审查
test_names.py 只断言可判定集合：完整性+显式 deny+保留字（覆盖当前完整命令面含 watch/cancel/abort/say/result/status）。对外口径=无显式 deny 词+无保留字，不声称无灰色词全覆盖。
保留字 deny：wait done list read test agent name ask clear doctor suggest status export import restore pane idle working blocked unknown hat hao herdr task token scope label role machine session tab workspace terminal send prompt focus split close attach config input layout move resize server start swap update open report view watch cancel abort say result。
灰色 deny：宗教/神秘 corona coven chapel censer bless karma creed faith oath angel spirit grace mercy pardon lamb dove revere saint fairy genie magic spell；暴力 combat bruise attack harm hurt abuse evil vice cull clash claw crack cringe crook crush；身体 diet beard brawn；族群/语言 greek roman latin kanji hanzi pinyin hangul kana hira hebrew arabic cyril thai hindi urdu farsi tamil telugu zulu maori。
allow-list：文学/叙事 myth saga fable tale verse prose story lyric sonnet rhyme stanza；自然/动物/工具/颜色/材质/食物中性词；伦理域抽象 blame shame misuse harden cynic opaque curb brake。round-4 watch→rook。完整性 40×40=1600 唯一全 4–6 小写无保留字无显式灰色。round-1 标历史勿重建。

## 15. 验收（逐命令/模式）
单元 stub+集成 named session（真实 split/label/start/restore/ask/wait/cancel/abort，echo+TUI 缩进正例）。
1. name w2:p9 hawk --scope api→hawk+hao-hawk-api
2. 别名 start temp 重开→restore adopt 改回 hawk；--no-adopt 跳过
3. label=yaml 不被 restore 碰
4. 两 hao-hawk→都歧义 exit6 不 rename；--pick 只恢复被选
5. hao-hawk-api/hao-hawk-web→name hawk 冲突 exit6
6. 另一 workspace 有 live hawk→本 workspace restore/name exit6
7. 预置哨兵/prompt 回显 wait 不成功；真实最终消息（TUI 缩进/⏺/尾部标点/代码框）命中；Bash tool hao done stdout→wait 看不到（已知限制）但台账/wake 副作用可用；token-only 引用不 busy-loop（正则要求邻接）；滚动顶出→超时重扫 fallback
8. machine fixture：list 两 shape/unknown/remote down/machine+session；本机无 profile 标注；result/wake 跨机器 experimental/不支持
9. suggest 3–5 中英文 task；live 重名扫 names+labels+stale
10. cancel 全模式停阻塞 wait exit10+幂等+迟到哨兵忽略+done-after-cancel 拒绝+token 不存在 exit3；abort blocked 无 TTY/0600 approval exit5（HAO_ABORT_ALLOW 不算）；超时 exit4 带状态尾部；blocked exit5
11. lifecycle 同步可 cancel：agent prompt 提交+自实现 5s working 门槛（未观察 exit9）+agent wait 短循环查台账；拒绝 async
12. file：partial 不提前返回；result 用台账 tombstone result_path+realpath，穿越被拒；shortid 12hex 防碰撞；completion 清理后 result 仍可读（tombstone）
13. wake 仅同机 hao done+台账可达生效，固定模板不含 summary；最终消息打印不产生 wake；caller blocked best-effort 丢失；caller 不存在 exit3；跨机器 caller 侧 poll
14. 台账 0700/0600+原子写+锁+tombstone 保 result_path+TTL 按 updated 不清 running+写失败降级；不 kill PID
15. status 默认当前 pane/say fire-forget 不写台账（blocked exit5/working best-effort）/result 读 tombstone；逐条 output/exit/JSON schema（protocol.md，含 done 例外）
16. test_names：完整性+保留字（全命令面）+显式 deny；list/doctor 默认当前 workspace+per-machine 标注

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
<details><summary>round-1（历史，勿重建）</summary>

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
r1 14m52s 哨兵回显误命中；r2 9m29s ^HAO_DONE TUI 缩进 false-negative→--match；r3 7m4s --match 命中+Bash tool stdout 不进 snapshot→canonical 最终消息；r4 5m17s 词表/匹配器全过余 9 条→v5；r5 4m0s 余 7 条（tombstone/wake 跨机器/lifecycle 阻塞矛盾/无 offset 游标/正则过严/abort env 非授权/TTL 误清）→v6 收口（server 侧容忍正则为主无游标、lifecycle 自实现门槛可 cancel、wake 限同机、abort TTY/0600、tombstone+TTL updated）。
forge 核实 herdr 0.9.5 命令面/label 持久化/词表完整性/agent name 规则/wait-output ^ 按行匹配/pane read 无 offset。
