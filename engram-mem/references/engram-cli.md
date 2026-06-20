# engram CLI 使用手册(engram-mem 参考)

本文件是 engram 命令行的完整参考。SKILL.md 在需要查具体命令/参数时指向这里,平时不必加载。

> 速记:`engram <command> [args]`。所有写入最终落到本地 `~/.engram/engram.db`(SQLite + FTS5)。

> ⚠️ 禁用命令:`engram setup <agent>`、`engram connect`、`engram mcp` 以及 `claude plugin install engram` 等会把 MCP/hook 写入 agent 配置——本方案"无 hook 纯 CLI",**禁止使用**(详见 SKILL.md「硬性禁止」段)。本手册只覆盖允许的 CLI 命令。

## 目录
- [save —— 保存记忆](#save)
- [search —— 检索记忆](#search)
- [context —— 取最近会话上下文](#context)
- [timeline —— 某条记忆的前后时间线](#timeline)
- [stats —— 统计](#stats)
- [delete —— 删除](#delete)
- [export —— 导出 JSON](#export)
- [sync —— 跨设备同步](#sync)
- [doctor / conflicts —— 诊断与冲突](#doctor)
- [scope 概念](#scope)
- [type 取值](#type)

---

## save
保存一条记忆。

```
engram save <title> <content> [--type TYPE] [--project PROJECT] [--scope SCOPE] [--topic TOPIC_KEY]
```

- `title`:简短英文标题(检索权重最高)
- `content`:正文(本技能里 = `[EN] 英文` + `[原文] 中文`)
- `--type`:从**固定 7 类**里选(见 [type 取值](#type),不要自造)
- `--project`:归属项目;不传则按当前目录(git 根)推断
- `--scope`:`project`(默认,按项目)或 `personal`(跨项目的个人记忆,适合日常生活)
- `--topic`:稳定的 `topic_key`,让同主题的演化笔记聚合

长/多行内容务必用带引号 heredoc 预拼,避免 shell 转义(见 SKILL.md 命令模板)。

---

## search
全文检索(FTS5,关键词,英文)。

```
engram search <query> [--type TYPE] [--project PROJECT] [--scope SCOPE] [--limit N]
```

- `query`:英文关键词(中文查询先译英)
- `--type` / `--project` / `--scope`:过滤
- `--limit N`:返回条数(默认有上限,召回不够时调大或换词重试)

技巧:没命中先**换关键词重试**再下结论;engram 按关键词密度排序、无语义兜底。

---

## context
注入/查看以往会话的最近上下文(用于"接着上次继续")。

```
engram context [project]
```

不带参数 = 当前项目;带项目名 = 指定项目。适合会话开始时唤回近期工作。

---

## timeline
围绕某条记忆看时间上前后发生了什么。

```
engram timeline <obs_id> [--before N] [--after N]
```

- `obs_id`:观察 id(search 结果里的 `#数字`)
- `--before/--after N`:前/后各取几条

---

## stats
查看记忆库统计(条数、项目、数据库路径等)。

```
engram stats
```

---

## delete
删除。默认软删除,`--hard` 永久删除。

```
engram delete <obs_id> [--hard]          # 删一条观察
engram delete session <id>               # 删一个 session(须无观察)
engram delete prompt <id>                # 删一条 prompt(永久)
engram delete project <name> [--hard]    # 级联删整个项目
```

---

## export
导出全部记忆为 JSON(备份/迁移)。

```
engram export [file]                     # 默认 engram-export.json
```

注意:`file` 是位置参数,别误传 `--help` 之类。

---

## sync
跨设备同步:本地 SQLite 为权威源,按项目导出压缩 chunk 到 `~/.engram/.engram/`,经 git 流转。

```
engram sync                              # 导出新记忆为 chunk(默认当前项目)
engram sync --all                        # 所有项目
engram sync --import                     # 在另一台机器导入新 chunk
engram sync --status                     # 查看同步状态
engram sync --cloud --project PROJECT    # 云复制(需显式 --project,可选)
```

git 闭环(配合 sync):

```bash
cd ~/.engram && git init && git remote add origin <私有仓>   # 一次性
engram sync --all && git -C ~/.engram add . && git -C ~/.engram commit -m "sync" && git -C ~/.engram push
# 另一台:git -C ~/.engram pull && engram sync --import
```

---

## doctor
只读诊断。

```
engram doctor [--json] [--project P] [--check CODE]
```

## conflicts
检视/管理"矛盾记忆"关系(同一主题前后说法冲突时)。

```
engram conflicts list [--project P] [--status S] [--limit N]
engram conflicts show <relation_id>
engram conflicts stats [--project P]
engram conflicts scan [--project P] [--dry-run | --apply] [--semantic]
```

`--semantic` 需要 `ENGRAM_AGENT_CLI`(claude/opencode);本技能日常不依赖它。

---

## scope
- `project`(默认):记忆归属某个项目/代码库,检索默认限定在当前项目。
- `personal`:跨项目的个人记忆。**日常生活类记忆(偏好、家人、计划、推荐)用 `--scope personal`**,在任何目录下都能搜到。
- **同步注意**:默认 `engram sync` 只导出当前项目,会漏 personal;**统一用 `engram sync --all`**(已实测:`--all` 才会导出 personal scope 记忆)。

---

## type
`--type` 技术上接受任意字符串,但本方案约定**固定 7 类**(不要自造,避免过滤碎片化):

| type | 含义 | 常见 scope |
|---|---|---|
| `decision` | 做了某选择 + 为什么 | project / personal |
| `bugfix` | 解决了某问题 + 根因 | project / personal |
| `discovery` | 学到/发现了什么 | project / personal |
| `preference` | 长期习惯/好恶 | personal |
| `person` | 关于某人的事实 | personal |
| `plan` | 未来的打算/行程/待办 | personal |
| `note` | 兜底:其它不归类 | 任意 |
