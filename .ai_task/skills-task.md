# 技能检查&优化

## 待办清单
- [ ] 检查所有技能是否符合 @anthropics/ 标准技能编写,检查技能对象目录：@mcp2cli/、@obsidian/、@superpowers/、@worktrunk/，将问题写入问题清单章节，将优化写入优化方案章节
- [ ] 检查所有技能是否有安全隐患

## 问题清单

### 1. Description 格式问题（严重）

根据 `@superpowers/writing-skills/SKILL.md` 标准，description 必须：
- 以 **"Use when..."** 开头
- 只描述触发条件，不描述工作流程
- 使用第三人称

**不符合要求的 Skills（8个）：**

| Skill | 当前 Description | 问题 |
|-------|-----------------|------|
| mcp2cli | "Turn any MCP server..." | 以功能描述开头，非 "Use when" |
| worktrunk | "Guidance for Worktrunk..." | 以"是什么"开头，非 "Use when" |
| defuddle | "Extract clean markdown content..." | 以功能描述开头，非 "Use when" |
| json-canvas | "Create and edit JSON Canvas files..." | 以功能描述开头，非 "Use when" |
| obsidian-bases | "Create and edit Obsidian Bases..." | 以功能描述开头，非 "Use when" |
| obsidian-cli | "Interact with Obsidian vaults..." | 以功能描述开头，非 "Use when" |
| obsidian-markdown | "Create and edit Obsidian Flavored Markdown..." | 以功能描述开头，非 "Use when" |
| brainstorming | "You MUST use this..." | 指令式开头，非 "Use when" |

**影响：** Claude 可能直接跟随 description 执行，而非完整阅读 skill 内容，导致遗漏关键流程细节。

### 2. Description 内容问题

部分符合格式的 description 存在内容问题：

| Skill | 问题 |
|-------|------|
| brainstorming | 包含工作流程暗示（"Explores user intent..."），应删除 |

### 3. 符合要求的 Skills（13个）

dispatching-parallel-agents、executing-plans、finishing-a-development-branch、receiving-code-review、requesting-code-review、subagent-driven-development、systematic-debugging、test-driven-development、using-git-worktrees、using-superpowers、verification-before-completion、writing-plans、writing-skills

### 4. 安全隐患问题

#### 4.1 有安全措施但可改进的 Skills

| Skill | 现有措施 | 潜在风险 | 改进建议 |
|-------|---------|---------|---------|
| **mcp2cli** | ✅ Security 章节：使用 env:/file: 前缀、信任边界警告 | 用户可能连接恶意 MCP server/API | 添加：连接前验证 URL 来源、敏感操作二次确认 |
| **worktrunk** | ✅ Hook approval 机制、dangerous patterns 警告 | dangerous patterns 定义不完整（仅列举 4 类） | 扩展危险模式列表、添加正则匹配规则 |

#### 4.2 缺少安全警告的 Skills

| Skill | 风险描述 | 严重程度 |
|-------|---------|---------|
| **obsidian-cli** | `obsidian eval code="..."` 可执行任意 JavaScript 代码 | ⚠️ 高 - 可能读取敏感数据、修改 vault |
| **defuddle** | 从任意 URL 获取内容，无 SSRF 防护警告 | ⚠️ 中 - 可能访问内网资源、泄露信息 |

#### 4.3 低风险/无风险的 Skills

| Skill | 原因 |
|-------|------|
| json-canvas | 仅编辑本地 .canvas 文件 |
| obsidian-bases | 仅编辑本地 .base 文件 |
| obsidian-markdown | 仅编辑本地 .md 文件 |
| superpowers 系列 | 方法论指导，不直接执行危险操作 |

---

## 优化方案

### 方案 1：修复 Description 格式（优先级：高）

为 8 个不合规的 skill 重写 description，确保以 "Use when..." 开头：

**mcp2cli:**
```yaml
# 当前
description: Turn any MCP server, OpenAPI spec, or GraphQL endpoint into a CLI...

# 优化后
description: Use when the user wants to interact with an MCP server, OpenAPI/REST API, or GraphQL API via command line, or when keywords include "mcp2cli", "call this MCP server", "use this API", "list tools from", "graphql"
```

**worktrunk:**
```yaml
# 当前
description: Guidance for Worktrunk (the `wt` CLI)...

# 优化后
description: Use when editing .config/wt.toml or ~/.config/worktrunk/config.toml, configuring hooks (post-merge, post-start, pre-commit, etc.), or troubleshooting wt behavior
```

**defuddle:**
```yaml
# 当前
description: Extract clean markdown content from web pages...

# 优化后
description: Use when the user provides a URL to read or analyze (excluding .md URLs), or needs to extract content from web pages, online documentation, articles, or blog posts
```

**json-canvas:**
```yaml
# 当前
description: Create and edit JSON Canvas files...

# 优化后
description: Use when working with .canvas files, creating visual canvases, mind maps, flowcharts, or when keywords include "canvas", "JSON Canvas"
```

**obsidian-bases:**
```yaml
# 当前
description: Create and edit Obsidian Bases...

# 优化后
description: Use when working with .base files, creating database-like views, or keywords include "Bases", "table views", "card views", "filters", "formulas"
```

**obsidian-cli:**
```yaml
# 当前
description: Interact with Obsidian vaults using the Obsidian CLI...

# 优化后
description: Use when the user asks to interact with their Obsidian vault, manage notes, search vault content, or develop/debug Obsidian plugins from command line
```

**obsidian-markdown:**
```yaml
# 当前
description: Create and edit Obsidian Flavored Markdown...

# 优化后
use: Use when working with .md files in Obsidian, or keywords include wikilinks, callouts, frontmatter, tags, embeds, Obsidian notes
```

**brainstorming:**
```yaml
# 当前
description: You MUST use this before any creative work...

# 优化后
description: Use before any creative work - creating features, building components, adding functionality, or modifying behavior
```

### 方案 2：清理多余描述内容

**brainstorming** 的 description 包含 "Explores user intent, requirements and design before implementation"，这是工作流程描述，应删除。

### 方案 3：添加安全警告章节（优先级：高）

**obsidian-cli** 需添加安全警告：

```markdown
## Security

- **eval command**: `obsidian eval code="..."` executes arbitrary JavaScript in the Obsidian app context. This can access vault files, read secrets, modify data. Use only for trusted development/debugging purposes.
- **Plugin reload**: Reloading untrusted plugins could execute malicious code.
```

**defuddle** 需添加安全警告：

```markdown
## Security

- **URL validation**: Defuddle fetches content from arbitrary URLs. Be cautious with:
  - URLs from untrusted sources (could be SSRF vectors)
  - URLs containing credentials or sensitive query parameters
- **Content trust**: Extracted content comes from external sources — treat as untrusted.
```

### 方案 4：扩展危险模式定义（优先级：中）

**worktrunk** 的 dangerous patterns 定义不完整，建议扩展：

当前定义的危险模式：
- `rm -rf`
- `DROP TABLE`
- `curl http://...`
- `sudo`

建议添加：
```markdown
**Dangerous patterns** — Warn users before creating hooks with:
- Destructive commands: `rm -rf`, `DROP TABLE`, `truncate`, `delete`, `unlink`
- External dependencies: `curl`, `wget`, `nc`, `ssh`, `scp`
- Privilege escalation: `sudo`, `su`, `doas`, `run0`
- Network exposure: `nc -l`, `python -m http.server`, `ngrok`
- File system modification: `chmod 777`, `chown`, `mkfs`
- Process manipulation: `kill -9`, `pkill`, `killall`
- Credential exposure: Commands containing passwords, tokens, keys in plaintext
```

### 执行顺序

1. **修复 Description 格式**（方案 1）- 8 个 skills
2. **添加安全警告**（方案 3）- obsidian-cli、defuddle
3. **扩展危险模式定义**（方案 4）- worktrunk
4. **清理多余描述内容**（方案 2）- brainstorming
5. 验证所有 frontmatter 总字符数 ≤ 1024
