---
name: engram-mem
description: >-
  基于本地 engram CLI(SQLite + FTS5)的跨会话持久记忆,工作与生活通用。当用户想
  「记住/记忆/记一下/存一下/别忘了/下次记得」某件事——一个决策、一次 bug 修复、一个
  偏好、一个计划、一个人、一件事、一个推荐(餐厅/书/工具)——或想「回忆/想不起来/
  我们之前怎么…/上次那个…怎么弄的/我之前记过吗/有没有处理过类似的」时,都要使用本技能。
  关键词包括「记忆、记住、记一下、想起来、回忆、笔记、之前、上次」等;即使没明说也常
  隐含存或搜记忆。场景不限于写代码,也覆盖日常生活(偏好、家人、计划、想法、推荐)。
  由于 engram 全文检索只切英文,本技能在存/搜前把中文译成英文,同时双存中文原文以保真。
  无 hook、无 MCP,纯 CLI。
---

# engram-mem

用本地 `engram` 二进制给 Claude 提供跨会话、跨设备的持久记忆——**工作和生活都能用**。
做完有价值的事(改完 bug、定了方案,或记住一个偏好、计划、推荐)就保存结构化笔记,
以后再检索。存储是本地 SQLite,跨设备同步走 git。

完整的 engram 命令/参数见 `references/engram-cli.md`(需要查具体用法时再读;本文给出主流程)。

## 决定一切的前提:engram 只能搜英文

engram 用 SQLite FTS5 的默认 `unicode61` 分词器,**不切分中文**——一段连续中文会变成一个
无法匹配的整 token,中文查询即使内容存在也返回 0(已实测)。英文则切分良好。

因此策略:**存一份英文用于检索,同时保留中文原文用于保真。** 翻译是模型擅长的事,还顺带
带来跨语言召回——英文记忆用中文或英文查询都能命中(查询时也译成英文)。

注意这是**关键词检索、非语义**:查 "stuck" 匹配不到写成 "frozen" 的笔记。所以同一概念
存和搜都用**同样的常用英文词**,以对抗这种漂移(见下方「翻译原则」)。

## 前置条件

`engram` 必须在 PATH(`brew install gentleman-programming/tap/engram`)。若
`engram --version` 失败,直接让用户安装,不要猜。

## 硬性禁止:绝不让 engram 写入 agent 的 MCP / hook 配置

本方案的根基是"无 hook、纯 CLI":只装 engram 二进制,只经 `engram` 命令读写记忆。
engram 另有一条"插件/集成"安装路径会把 **MCP server + lifecycle hooks** 注入到 agent
(Claude Code / Codex / Gemini CLI 等)的配置里——**这条路径在本方案中禁止使用**,因为
hook 会带来后台自动捕获、常驻上下文成本和不可控行为,正是我们要避开的。

**禁止执行**(以下命令/操作都会写入 MCP 或 hook,一律不要跑):

- `engram setup <agent>`(如 `engram setup claude-code` / `opencode` / `codex` / `gemini-cli` / `pi`)
- `claude plugin marketplace add Gentleman-Programming/engram` 及 `claude plugin install engram`
- 任何把 `engram mcp` 写进 `~/.claude.json`、项目 `.mcp.json`、或 settings `hooks` 的操作
- `engram connect ...` / `--with-hooks` 之类的接线命令

**允许**:仅 `brew install .../engram`(或下载二进制),然后通过本 skill 用 CLI 调用。

### 自检(确认没被写入)

若怀疑被注册过,用下面命令检查并清理(发现 engram 条目应移除):

```bash
# Claude Code:全局与项目 MCP 配置里不应出现 engram
grep -i engram ~/.claude.json 2>/dev/null
grep -ri engram ./.mcp.json ./.claude/settings*.json 2>/dev/null
# 其它 agent 同理检查各自配置(~/.codex、~/.gemini、opencode.json 等)
```

预期:**无任何 engram MCP/hook 输出**。若有,说明误用了 setup/插件路径,需手动删掉相应条目。

## 激活策略(何时存、何时取)

前提:无 hook,激活靠"请求/判断"驱动,不会每会话自动跑。以下规则界定 Claude 应在何时
主动出手——既不漏掉值得记的,也不制造噪声。

### 存(save):显式 + 主动建议,**点头才存,绝不静默自动存**

- **用户显式要求**时直接存:「记一下/记住/别忘了/存一下」。
- **到达明显节点时主动问一句"要记下这条吗?"**,得到确认再存。这些节点是:
  - 解决了一个**非平凡**的 bug(有根因、有非显然的解法)
  - 做了一个**决策**(架构/方案/选型)并有理由
  - 用户陈述了一个**长期偏好 / 计划 / 关于某人的事实**(如"我习惯…""下周要…""我老婆对…过敏")
  - **发现**了不显然、以后还会用到的东西
- **不要**为琐碎、一次性、马上过期的内容提议保存——主动是为了不漏重点,不是把什么都记。
- 永远不自动静默保存(那是被否掉的 hook 行为);保存前给用户一句话确认的机会。

### 取(recall):相关即主动搜,**先搜再答**

当任务/问题**看起来可能有旧上下文**时,先搜记忆再回答/动手:

- 在某项目里继续工作 → 用该项目搜近期相关记忆
- 用户问"我们怎么处理 X 的 / 之前定的方案 / 我之前记过吗 / 有没有类似的"
- 遇到一个**像是以前解决过**的问题
- 涉及可能存过的**个人偏好 / 计划 / 某人信息**(用 `--scope personal` 搜)

保持轻量:搜一次,没命中换关键词再试一次,然后照常推进——不要因为没搜到就卡住。
对明显全新、与历史无关的问题,不必搜(避免无谓调用)。

> 触发词(供 description 匹配):存「记住/记忆/记一下/存一下/别忘了/下次记得」;
> 取「回忆/想起来/想不起来/之前/上次/笔记/我们怎么…/我之前…」。

## 保存记忆(save)

1. **提炼**:浓缩成简短结构化笔记,存决策/事实/心得及其**原因或要点**,别存原始对话。
2. **翻译成英文**:写英文标题 + 完整英文正文;技术词、人名、品牌、专有名词原样保留
   (见翻译原则)。原文本就是英文则无需保留中文。
3. **组装**:按下面布局拼 title + content。
4. **执行** `engram save`,并选好 `--type` 与 `--scope`。

### 存储布局

- **title**:简短、关键词丰富的**英文**标题(检索权重最高,把最值得搜的词放这)。
- **content**:`[EN]` 块(完整英文,被检索)+ `[原文]` 块(中文原文,保真;不可检索也不误命中)。
- **--type**:从下面这**固定 7 类**里选(不要自造,避免过滤碎片化;实在不归类用 `note`):

  | type | 含义 | 常见 scope |
  |---|---|---|
  | `decision` | 做了某选择 + 为什么 | project / personal |
  | `bugfix` | 解决了某问题 + 根因 | project / personal |
  | `discovery` | 学到/发现了什么 | project / personal |
  | `preference` | 长期习惯/好恶(自己或他人) | personal |
  | `person` | 关于某人的事实 | personal |
  | `plan` | 未来的打算/行程/待办 | personal |
  | `note` | 兜底:其它不归类的事实 | 任意 |

- **--scope**:**代码/项目相关 → `project`(默认)**;**日常生活相关 → `personal`**(跨项目,
  任何目录下都搜得到,不被项目边界切开)。两者的 sync 见下方「跨设备同步」——统一用 `--all`。
- **--topic**(可选):会演化的主题给个稳定 `topic_key`,让同主题笔记聚合。

搭配习惯:代码记忆多为 `decision/bugfix/discovery` + `--scope project`;生活记忆多为
`preference/person/plan/note` + `--scope personal`。

### 命令模板

短的单行内容——直接传参:

```bash
engram save "Prefer pnpm over npm" \
  "[EN] Use pnpm not npm; faster, cleaner hoisting in monorepos. [原文] 习惯用 pnpm 而非 npm:更快、monorepo 下依赖提升更干净。" \
  --type preference --scope personal --topic package-manager
```

生活场景示例(用 personal scope):

```bash
engram save "Wife allergic to peanuts and shellfish" \
  "[EN] Wife is allergic to peanuts and shellfish — avoid when booking restaurants or cooking. [原文] 老婆对花生和贝类过敏,订餐厅、做饭都要避开。" \
  --type person --scope personal
```

较长或多行内容——先用**带引号 heredoc** 拼好 content,避免 shell 转义(`$`、反引号、引号):

```bash
CONTENT="$(cat <<'EOF'
[EN]
Fixed login timeout: wrapped JWT validation in retry with exponential backoff.
Root cause was clock skew causing tokens to expire early.

[原文]
修复登录超时:把 JWT 校验包了重试和指数退避。根因是时钟偏移导致 token 提前失效。
EOF
)"
engram save "Fix login timeout via JWT retry and backoff" "$CONTENT" --type bugfix --topic auth-timeout
```

保存后用分配到的 id 加一句话摘要向用户确认。

## 检索记忆(recall)

检索是**关键词精确匹配、无语义兜底**,所以"召回靠多试、别过早过滤、别过早放弃"。
实测教训:一条明明存在的记忆,因第一次查询词不对 + 误加了 scope 过滤,前三次全返回 0,
第四次换词才命中——差点被误判成"没存过"。据此定下面的规则。

1. **把查询译成英文**(用与保存时一致的常用词);用户给英文则直接用。
2. **第一次搜:宽,不要加 `--scope` 过滤。** scope(project/personal)很难猜准,猜错会把
   命中的记忆直接滤掉。先搜全量,拿到结果再按需收窄。
3. **多轮换词,至少试 2-3 个角度再下"不存在"结论**。换词思路:
   - 用户的**原词直译** + 明显**近义词**(分类→classify / categorize / lists / organize)
   - 可能出现在记忆里的**具体名词/专名**(库名、API、项目名、功能名,如 "star lists"、"GraphQL")
   - 放宽到**单个核心词**(如只搜 "star"、"stars")
4. **可读地呈现**;用户用中文时把 `[原文]` 中文一并展示。
5. 仅在确实需要收窄时才加过滤:`--type` / `--project` / `--scope` / `--limit`。

```bash
engram search "github star lists" --limit 10      # 第一次:宽,不加 scope
engram search "star categorize organize" --limit 10   # 没中就换词再试
engram search "wife allergy food" --limit 10      # 确认是生活记忆后再 --scope personal 收窄
```

## 翻译原则

翻译用**标准、惯用**的英文术语(Claude 对常见词的译法本就稳定,不需要查表);只要同一概念
存与搜都用同样的常用词,就能对上。

**绝不翻译**代码标识符、库/工具名、报错串、API 名、人名、品牌——`JWT`、`Redis`、`N+1`、
`useEffect`、`TypeError` 等原样保留。它们本就是最好的检索键,也让纯中文内容的笔记在没有
英文块时也能被搜到。

## 跨设备同步(简版)

engram 以本地 SQLite 为权威源,通过 git 同步。完整命令见 `references/engram-cli.md`。

**两条铁律:**
1. **`engram sync` 把 chunk 写到「当前目录/.engram」**(源码里是相对路径 `.engram`,无法用 flag 改)。
   所以**必须在 `~/.engram` 里跑**;在别处跑会把 chunk 写进那个目录的 `.engram/`(如
   `~/Code/某项目/.engram/`),既不进数据目录也没进 git 仓——记忆看似同步了实际丢了。
   (这是实测踩过的坑。)
2. **`engram sync` 要带 `--all`**:默认只导出当前项目,会漏 `--scope personal` 的生活记忆;
   `--all` 才导出全部(含 personal)。

为彻底免踩 cwd 坑,**同步统一走 skill 自带脚本** `scripts/engram-sync.sh`(它内部用子 shell
固定到 `~/.engram`,既保证 chunk 落对地方,又不改你当前目录):

```bash
# 路径相对本 skill 目录;<skill> = 本 SKILL.md 所在目录
<skill>/scripts/engram-sync.sh push      # engram sync --all → git add/commit/push(默认)
<skill>/scripts/engram-sync.sh pull      # git pull → engram sync --import
<skill>/scripts/engram-sync.sh status    # engram 同步状态 + git 状态
```

首次每台机一次性初始化 git 远端(脚本不做这步,避免误操作):

```bash
( cd ~/.engram && git init && git remote add origin <私有仓> )   # 用私有仓!
```

务必用**私有**仓(记忆含敏感上下文)。检索文本已是英文,同步后各机表现一致;继续用同样的常用译词即可对齐。

> 注:`engram sync --status` 里的 `Remote chunks` 指的是 engram 自建 cloud 服务(未配置即为 0),
> 与"git 已推送成功"无关——本方案的云端走 git→GitHub,不是 engram cloud。
> 脚本可用 `ENGRAM_HOME` 覆盖数据目录(默认 `~/.engram`)。

## 为什么这样设计(便于变通,而非死记)

- **CLI 而非 MCP**:不在上下文常驻、无后台 hook、每个动作都是可检视的 shell 命令。
- **先翻译再存**胜过中文分词 hack:engram 纯 Go 无法加载 C 分词扩展(jieba/ICU),内置
  trigram 会漏 2 字词还可能破坏更新;翻译绕开这一切且零依赖。
- **双存**用一点冗余换信任:随时能读原始措辞、核对翻译没走样。
- **工作与生活通用**:固定 7 类 `type` + `--scope personal` 让它不止服务编码,也能记住
  生活里的偏好、计划、人和事。
