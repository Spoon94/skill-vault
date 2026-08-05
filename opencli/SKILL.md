---
name: opencli
description: OpenCLI 全能助手 - 把任意网站/Electron 应用/外部 CLI 变成 `opencli <site> <command>` 的统一操作面。当 agent 要读写已登录网站、驱动真实浏览器、抓取页面、填表点击、修复失效适配器、给新站点写适配器、维护站点 sitemap、或把搜索/查询路由到最佳数据源时，都用这个 skill。这是合并了 7 个官方 opencli 子技能（usage/browser/adapter-author/sitemap-author/browser-sitemap/autofix/smart-search）的统一入口，按任务类型路由到对应章节或 reference。
allowed-tools: Bash(opencli:*), Bash(gh:*), Read, Edit, Write, Grep
---

# opencli

你是用 OpenCLI 干活的 agent。这个 skill 把 7 个官方子技能合并成一处：先在这里定位任务类型，再去对应章节或 reference 读细节。不要一次性把所有 reference 都读进上下文。

OpenCLI 把任意网站、Electron 桌面应用、或外部 CLI 变成统一的 `opencli <site> <command>` 操作面，agent 无需屏幕抓取即可驱动。

## 任务路由 - 先定方向

按任务类型选入口：

| 任务 | 直接读 | 完整手册 |
|---|---|---|
| 读已登录站点数据 / 找对命令 / "opencli 能干嘛" | 下方「§快速上手」 | - |
| 驱动真实浏览器（点击/填表/抓取，无适配器或临时） | 下方「§浏览器原语核心」 | `references/browser.md` |
| 适配器命令失败了要修 | 下方「§适配器失效自动修复」 | `references/autofix.md` |
| 给新站点写适配器 / 给现有站点加命令 | `references/adapter-author.md` | `references/adapter/` |
| 用 sitemap 驱动多步站点流程 | `references/browser-sitemap.md` | - |
| 创建/维护站点 sitemap | `references/sitemap-author.md` | `references/sitemap/sitemap-schema.md` |
| 把搜索/查询路由到最佳数据源 | 下方「§智能搜索路由」 | `references/search/` |

---

## §快速上手

### 三大支柱

- **适配器命令** - `opencli <site> <command> [...]`。内置适配器在 `clis/`，用户私有适配器在 `~/.opencli/clis/`。每个命令有 strategy 标签（`public | cookie | intercept | ui | local`，`opencli list -f json` 输出小写），告诉你是否需要 Chrome。
- **浏览器驱动** - `opencli browser *`（`open`/`state`/`click`/`type`/`select`/`find`/`extract`/`network`…），适配器没覆盖时临时用。
- **当前标签绑定** - `opencli browser <session> bind` 把用户已经打开并登录的标签绑到会话，后续用 `opencli browser <session> ...` 操作。详见 `references/browser.md`。
- **外部 CLI 透传** - `opencli gh`、`opencli docker` 等，用 `opencli external install <name>` 管理。

### 安装与体检

```bash
# npm 全局安装（推荐，需 Node >= 20）
npm install -g @jackwener/opencli

# 从源码跑（无全局安装）
git clone git@github.com:jackwener/OpenCLI.git
cd OpenCLI && npm install
npx tsx src/main.ts <command>               # 同 npm 版操作面

opencli doctor                              # 浏览器相关任务前必跑
```

`opencli doctor` 诊断**浏览器桥**（daemon + 扩展 + Chrome 接线），范围窄：`public`/`local` 适配器、`opencli list`、插件、外部 CLI 透传不需要它绿；只有 `cookie`/`intercept`/`ui` 适配器和 `opencli browser *` 需要。失败常见原因：Chrome 没开、扩展没装、调试端口被 1Password 等扩展占用。

### Shell completion

```bash
opencli completion bash   # 也支持 zsh / fish，输出到 stdout，按 shell 惯例 source 或保存
```

### 其他顶层命令

```bash
opencli daemon status|stop|restart    # 管理 opencli 后台 daemon
opencli auth status|refresh           # 看登录态 / 刷新已登录站点会话保活
opencli skills list|read              # 列出 / 读取捆绑的 opencli-* 技能
opencli convention-audit [target]     # 扫描适配器是否符合 agent-native 约定（开发者用）
```

### 全局 flag

| flag | 作用 |
|---|---|
| `--profile <name>` | 所有命令可加，路由到指定 Chrome profile 别名（等价于 `OPENCLI_PROFILE`） |

### 按 strategy 看命令需要什么

| `opencli list` 上的 strategy 标签 | 需要什么 |
|---|---|
| `public` | 无 - 纯 HTTP，不碰浏览器 |
| `cookie` | Chrome 登录目标站点 + 装扩展，命令从 live session 取凭证，不用重登 |
| `intercept` | 同 cookie，加开一个自动化窗口抓签名请求 |
| `ui` | 同 cookie，完整 DOM 交互 |
| `local` | 无浏览器，连本地/dev 端点 |

Electron 桌面应用（cursor/codex/chatwise/discord-app/doubao-app/antigravity/chatgpt-app）走 CDP 连运行中的应用，同 cookie-less 流程，调用前确保应用在跑。

### ⚠️ 适配器返回 `[]` / 空时怎么排查

带 `domain` 的 `cookie` 适配器（如 `zhihu hot`）会**自己先导航**到 `https://<domain>` 再取数，不依赖前台标签。返回空时按序排查：

1. **先重跑一次** - 首次连接/冷启动偶发空结果，重跑即恢复（实测：前台 `about:blank` 时 `zhihu hot` 也正常）。
2. **查登录态** - 用 `opencli browser <session> open https://<site>/` 打开站点，看是否跳登录页；跳了就在 Chrome 里登录。
3. **换查询/入口重试** - 平台反爬降级、软 404 会返回结构正常但空的 payload（见「§适配器失效自动修复」的"空 ≠ 坏了"）。
4. 以上都排除仍复现，才进 `--trace retain-on-failure` 修复流程。

真正依赖当前页面状态的是**无 domain 的 `ui` 适配器**（如 antigravity 等桌面 App 操作，`navigateBefore=true`，不预导航直接操作当前页面）——用它们时确保目标 App/页面已在运行。

`public`/`local` 适配器不碰浏览器（`browser: false`，Node 侧纯 fetch 或连本地端点），不带浏览器 cookie，与前台标签无关。

### 发现命令 - 别读文档，跑命令

```bash
opencli list                    # 表格，按站点分组
opencli list -f json            # 机器可读；喂给 jq 或 agent
opencli list | grep -i twitter  # 找某站点的命令
opencli <site> --help           # 看该站点的子命令 + flag
opencli <site> <command> --help  # 看位置参数和命令专属 flag
```

别硬编码适配器列表 - 100+ 站点每周都在变。`opencli list -f json` 是真相源，每条命令一个 entry，含 `{site, name, aliases, description, strategy, browser, args, columns, ...}`。

### 通用 flag（每个适配器命令都生效）

| flag | 作用 |
|---|---|
| `-f, --format <fmt>` | `table`（TTY 默认）· `yaml`（非 TTY 默认）· `json` · `md` · `csv`。agent 几乎总用 `-f json` |
| `-v, --verbose` | 调试日志 + 失败堆栈 |

命令专属 flag（`--limit`/`--tab`/`--filter`…）不通用，看 `<site> <command> --help`。

### 环境变量

| 变量 | 默认 | 用途 |
|---|---|---|
| `OPENCLI_BROWSER_CONNECT_TIMEOUT` | `45` | 等浏览器桥的秒数 |
| `OPENCLI_BROWSER_COMMAND_TIMEOUT` | `60` | 单命令超时 |
| `OPENCLI_CDP_ENDPOINT` | - | 手动 CDP 端点（远程 Chrome / Electron） |
| `OPENCLI_CACHE_DIR` | `~/.opencli/cache` | 网络抓取 + 浏览器状态缓存 |
| `OPENCLI_CONFIG_DIR` | `~/.opencli` | 覆盖 opencli 配置目录（browser-profiles.json 等存这里） |
| `OPENCLI_WINDOW` | 命令专属 | `foreground` / `background` 浏览器窗口模式 |
| `OPENCLI_PROFILE` | - | 路由到指定 Chrome profile 别名（见「§profile 路由」） |
| `OPENCLI_VERBOSE` | `false` | 详细日志（`-v` 也触发） |

### profile 路由

opencli 的 "profile" **不是** Chrome 的 user profile，而是扩展自己生成的 8 位随机 contextId，每装一次扩展生成一个。

```bash
opencli profile list                    # 当前运行 + 连着的 context
opencli profile rename <contextId> bot  # 给 context 起好记的别名
opencli profile use <alias>             # 设默认 profile（软偏好，离线时回落到唯一连着的）
OPENCLI_PROFILE=bot opencli <site> <cmd>  # 显式路由（离线会大声报错）
```

无人值守/自动化走专用 `bot` profile，隔离误操作；交互式留在默认 profile。

---

## §浏览器原语核心

适配器没覆盖时，用 `opencli browser *` 临时驱动。完整原语手册见 `references/browser.md`，这里只放核心决策规则。

### 前置

```bash
opencli doctor   # 没绿啥都干不了
```

### 会话生命周期

- `opencli browser *` 命令在 `browser` 后接一个 `<session>` 位置参数。多步流程用同一 session 名；隔离并行工作用不同名。
- 临时会话：`opencli browser <session> open <url>` ... `opencli browser <session> close`。
- 绑定已开标签：`opencli browser <session> bind`（用户已登录/已定位的标签）。
- `--window foreground|background` 控制是否前台聚焦窗口。

### 四条心智模型

1. **target 优先用数字 ref。** 每个交互命令（`click`/`type`/`select`/`get`）接一个 `<target>`，是 `state`/`find` 输出的 `[N]` 数字 ref **或** CSS 选择器。CSS 多匹配时用 `--nth <n>` 消歧。
2. **每个信封都报 `matches_n` 和 `match_level`。** `match_level` 是 `exact`/`stable`/`reidentified` - CLI 已经替你救了中度 DOM 漂移，level 告诉你该多信。
3. **紧凑输出优先，完整 payload 按需取。** `state` 是预算快照；`get html --as json` 支持 `--depth/--children-max/--text-max`；`network` 返回 shape 预览，用 `--detail <key>` 取单个 body。
4. **结构化错误可机读。** 失败时输出 `{error: {code, message, hint?, candidates?}}`，按 `code` 分支，别按 message 字符串。

### match_level 速查

| level | 含义 | 你该 |
|---|---|---|
| `exact` | 指纹完全对上 | 继续 |
| `stable` | 强 ID 还在，软信号（aria-label/role/text）漂了 | 继续；若写操作内容重要，`get value` 复查 |
| `reidentified` | 原 ref 没了，CLI 找到唯一替代重新打了旧 ref | 复查是不是对的元素再继续 |

### 十条关键规则

1. **先看后动。** 先 `state` 或 `find`，别跨会话记 ref/选择器（索引是按快照的）。
2. **优先站点适配器，别上来就裸开浏览器。** `opencli <site> <command>` 能覆盖就用，`opencli browser ...` 只补缺口。
3. **拿到 ref 后优先用数字 ref。** ref 比 CSS 抗 DOM 漂移。
4. **每次写操作后读 `match_level`。** `exact` 没事；`stable` 内容重要就复查；`reidentified` 必查。
5. **表单控件用 `compound` 字段。** 别正则猜日期格式，别 `state` 两次取 `<select>` 选项列表。
6. **写操作要验证。** `type` 后跑 `get value`；`select` 后跑 `get value`。自动补全/React 受控输入/掩码字段会静默吃字符，CLI 检测不到。
7. **页面变化后 `state` -> action -> `state`。** 导航/表单提交/SPA 路由会让 ref 失效，重新快照。
8. **复用刚解析的 ref 时用 `&&` 串联。** 串联在一个 shell 里跑，ref 能直接传给下一条命令。
9. **`eval` 只读。** JS 包 IIFE 返回 JSON；要改页面用 `click`/`type`/`select`/`keys`，它们产结构化输出和指纹，`eval` 不产。
10. **优先 `network` 而非屏幕抓取。** 页面数据来自 JSON API 时，API 比抓 DOM 可靠得多。

### 常用命令速查

| 命令 | 用途 |
|---|---|
| `browser state` | 快照：文本树 + `[N]` ref + `compounds (N):` 边栏 |
| `browser state --source ax` | 无障碍树快照（自定义控件/portal/iframe 用） |
| `browser find --css <sel>` | CSS 查询，比 `state` 便宜 |
| `browser find --role button --name Save` | 语义定位查询 |
| `browser click/type/select <target>` | 交互（返回 match_level） |
| `browser get text/value/attributes <target>` | 读单字段 |
| `browser network` | API shape 预览 + 缓存 key 列表 |
| `browser network --detail <key>` | 取单个 cached body |
| `browser extract` | 长文 Markdown 抽取（带 `next_start_char` 游标） |
| `browser eval <js>` | 页面内只读 JS |
| `browser wait selector/text/download` | 等条件 |
| `browser tab list/new/select/close` | 标签管理 |
| `browser <session> bind/unbind` | 绑/解当前标签 |
| `browser screenshot --annotate` | 可视化 ref 地图（图标控件/图表用） |

### 结构化错误码（按 code 分支，别按 message）

| code | 含义 |
|---|---|
| `not_found` | 数字 ref 不在 DOM 了，重新 `state` |
| `stale_ref` | ref 在但元素变了身份，重新 `state` |
| `invalid_selector` | CSS 被 `querySelectorAll` 拒了 |
| `selector_not_found` | CSS 匹配 0 个，用 `find` 换更松的选择器 |
| `selector_ambiguous` | CSS 匹配 >1 且没 `--nth` |
| `option_not_found` | `select` 没找到选项，信封含 `available: string[]` |

完整命令参考、compound 表单控件、cost guide、recipes、pitfalls 见 `references/browser.md`。

---

## §适配器失效自动修复

`opencli <site> <command>` 因网站改版失败时，**别只报错，自动诊断 + 修适配器 + 重试**。完整流程见 `references/autofix.md`，这里放关键边界。

### 硬停（不修代码）

- **`AUTH_REQUIRED`**（exit 77）- 停。告诉用户去 Chrome 登录站点。
- **`BROWSER_CONNECT`**（exit 69）- 停。告诉用户跑 `opencli doctor`。
- **CAPTCHA / 限频** - 停，不是适配器问题。

### "空" ≠ "坏了"

`EMPTY_RESULT` 常常**不是适配器 bug**：平台反爬降级、软 404（HTTP 200 + 空 payload）、搜索"0 结果"是合法答案。修前先：

- 换查询或入口重试（`search "X"` 空但 `search "X 攻略"` 满 = 适配器没坏）
- 正常 Chrome 标签里肉眼看一眼数据在不在
- 隔 2-3 秒重试区分"临时隐藏"和"真没了"

只有空/缺结果**跨重试和替代入口都能复现**，才进修复流程。

### 修复流程（最多 3 轮）

1. **收 trace**：`opencli <site> <cmd> [args] --trace retain-on-failure 2>trace-error.yaml`，读 stderr 里的 `trace.summaryPath`。
2. **分析**：读 `summary.md`（含 `adapterSourcePath` front matter）+ 适配器源码，按错误码归类（SELECTOR/EMPTY_RESULT/API_ERROR/TIMEOUT/PAGE_CHANGED）。
3. **探活站**：用 `opencli browser <session> state`/`network` 看当前真实 DOM/API，**别用坏掉的适配器**。
4. **打补丁**：只改 `adapterSourcePath` 指向的那一个文件，最小改动，保持 `columns` 输出结构，优先 API over DOM，只用 `@jackwener/opencli/*` import。
5. **验证**：重跑 `opencli <site> <cmd>`，还失败回第 1 步取新 trace。3 轮耗尽就停并报告。
6. **报上游**：验证通过后，本地适配器已偏离 upstream，按模板起 GitHub issue，**问用户确认后**再用 `gh issue create --repo jackwener/OpenCLI` 提交。

完整步骤、常见修复模式、issue 模板见 `references/autofix.md`。

---

## §智能搜索路由

用户要搜索/查询/查找/研究信息时，按话题和场景把查询路由到最佳 opencli 搜索源。核心不是记命令，而是**先定位数据源，再用 `opencli ... -h` 读实时帮助**，避免文档漂移。

### 强制预检（每次都要做）

选定站点前：
- `opencli list -f yaml` 用 live registry 确认候选站点存在，检查 `strategy`/`browser`/`domain`

选定站点后：
- `opencli <site> -h` 看子命令
- 锁定子命令后再 `opencli <site> <command> -h` 看参数/输出列/策略

别在 skill 里硬编码参数或假设命令签名，以 `-h` 实时输出为准。

### 主路由规则

1. 用户明确指定网站/平台/数据源 -> 直接用对应站点。
2. 用户没指定网站 -> 优先只选一个 AI 源：`grok` / `doubao` / `gemini` 三选一。
3. AI 返回不足 / 缺原始数据 / 需权威佐证 / 需垂直结果 -> 再补 1-2 个专用源。

### AI 源选择

- `grok` - 实时讨论、英文舆论、Twitter/X 语境、热点追踪
- `doubao` - 中文语境、字节抖音生态、生活方式、中文热点
- `gemini` - 全球网页、英文资料、通用检索、背景综述

没指定网站时，先判语言语境，从这三选一。**同一题内每个 AI 站点最多调 1 次**，别反复追打。

### 单题预算

- `opencli list -f yaml`、`-h` 类帮助不计入搜索次数
- 一次真正的 `opencli <site> ...` 执行 = 该站点 1 次调用（失败也算）
- AI 站点：同题内每站最多 1 次
- 非 AI 站点：默认最多 2 次；第 2 次必须有明确理由（第一次过宽要加时间/地区/类别/关键词限定）；不要第 3 次
- 限频后：记录"已跳过：<site> 达到频率上限"，换同类站点或基于已收集信息回答并说明缺口

### 查询词构造（AI 源）

别只丢短关键词，构造"主题 + 目标 + 限定条件"：`<主题> + <你要回答的问题>` / `<主题> + <时间/地区/语言>` / `<主题> + <平台范围>` / `<主题> + <输出要求>`。

### 查询结束汇报

回答末尾追加"搜索摘要"：

```md
搜索摘要
- 网站：<site1> | 查询词：<term1> | 次数：<n>
- 网站：<site2> | 查询词：<term2>；<term3> | 次数：<n>
- 已跳过：<site3>，原因：达到频率上限
```

各垂直源（技术/社交/媒体/资讯/购物/旅游等）的分类清单见 `references/search/sources-*.md`，按需读对应文件。

完整搜索路由规则、单题预算与频率限制、AI 查询词构造、查询结束汇报模板见 `references/smart-search.md`。

---

## §写自己的适配器

要给新站点写适配器、或给现有站点加命令，读 `references/adapter-author.md` 走完整 runbook（从侦察到 `opencli browser verify` 闭环）。关键约定：

- 私人适配器放 `~/.opencli/clis/<site>/<name>.js`（免 build）；要提 PR 才 copy 到 `clis/<site>/`
- 只 import `@jackwener/opencli/registry` + `@jackwener/opencli/errors`
- `columns` 数组和 `func` 返回对象 keys 完全对齐（含顺序）
- `browser:` field 决定 func 签名：`browser:false -> (args)`，`browser:true -> (page, args)`
- 已知失败按 typed error 分类抛，别 silent `return []` 或 sentinel row
- 调试 dump 只能落在 `~/.opencli/sites/<site>/fixtures/` 或 `/tmp/`，严禁留在 repo 根或 `clis/`

strategy 选择（`PUBLIC_API/COOKIE_API/PAGE_FETCH/INTERCEPT/DOM_STATE/UI_SELECTOR`）、字段解码、site-memory 回写等细节见 `references/adapter/` 下对应文件。

### 适配器管理命令

```bash
opencli adapter status              # 看哪些站点有本地覆盖 vs 用官方基线
opencli adapter eject <site>        # 把官方适配器 copy 到 ~/.opencli/clis/ 供本地编辑
opencli adapter reset [site]        # 删本地覆盖，恢复官方版本
opencli validate [target]           # 语义检查注册表（description/domain/pipeline/args 等），无网络
opencli verify [target] [--smoke]   # 验证 + 冒烟测试
opencli browser verify <site>/<name> # 在浏览器桥里端到端冒烟（init/verify 不需要 session）
```

---

## §用 sitemap 驱动 / 写 sitemap

`opencli browser <session> open` 或 `analyze` 报 `sitemap.available: true` 时，读 `references/browser-sitemap.md` 用 sitemap 指导多步流程。sitemap 是**先验知识不是真相**，浏览器实状态和 sitemap 冲突时信浏览器。

要创建/维护站点 sitemap，读 `references/sitemap-author.md`（schema 细节见 `references/sitemap/sitemap-schema.md`）。

---

## §外部 CLI 透传 / 插件

```bash
opencli external install gh                           # 按 external-clis.yaml 自动装
opencli external register my-tool --binary my-tool --install "npm i -g my-tool" --desc "..."
opencli external list [-f json]                       # 看已注册的外部 CLI
opencli gh pr list --limit 5                          # 透传，stdio 继承，exit code 透传

opencli plugin install github:user/repo    # 装插件
opencli plugin list [-f json]              # 看已装
opencli plugin update [name] | --all       # 更新
opencli plugin uninstall <name>            # 卸载
opencli plugin create <name>               # 脚手架生成新插件
```

内置 external 在 `src/external-clis.yaml`，用户覆盖在 `~/.opencli/external-clis.yaml`。

---

## 已废弃命令（别再调）

以下在 PR #1094 合并被移除：

- `opencli explore <url>` - 用 `opencli browser <session> network` + `find` 替代
- `opencli record <url>` - 用 `opencli browser <session> network --detail` 替代
- `opencli web read` / `opencli desktop *` 作为顶层命令组 - 已并入各自适配器（`opencli web read` 仍作为 `web` 适配器的 `read` 子命令存在，但没有独立的 `web`/`desktop` 顶层命令组）

---

## 红线

- 别把这个 skill 的命令列表贴进计划，会 rot。任务开始时跑 `opencli list -f json`。
- 别假设每个适配器都需要浏览器 - `public` 和 `local` 不需要，看 `strategy` 字段。
- 别把失败适配器静默回退到手写 `fetch` - 先 `--trace retain-on-failure` 取浏览器证据和适配器源路径。
- 别为了 "API-first" 把稳定的 UI/DOM 实现盲目迁到无契约内部接口（`PAGE_FETCH`/`INTERCEPT` 的 fix 频率约 `PUBLIC_API` 的 7-8 倍）。
- 写操作默认先确认再执行（发帖/回复/删除等）。
