---
name: git-commit
description: 'Use when writing Git commit messages, reviewing commits, or setting up commit message linting. Keywords: commit message, git commit, commitlint, semantic versioning, commit format.'
---

# Conventional Commits

规范 Git 提交信息格式，便于自动化工具生成版本号、变更日志。遵循 [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) 与 [Angular 提交规范](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#commit)。

## 何时使用

- 编写 Git 提交信息
- 创建代码提交
- 审查提交历史
- 生成提交信息模板

## 核心格式

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Type 类型（必须）

| Type | 含义 | SemVer 影响 |
|------|------|-------------|
| `feat` | 新功能 | MINOR |
| `fix` | Bug 修复 | PATCH |
| `docs` | 文档变更 | 无 |
| `style` | 格式调整（不影响逻辑） | 无 |
| `refactor` | 重构（非新功能、非修复） | 无 |
| `perf` | 性能优化 | PATCH |
| `test` | 测试相关 | 无 |
| `build` | 构建流程、依赖变更 | 无 |
| `ci` | CI/CD 配置变更 | 无 |
| `chore` | 其他杂项 | 无 |
| `revert` | 回退提交（如 `revert: feat(api-key)`） | 无 |

**其他类型允许**，但不影响语义版本（除非含 BREAKING CHANGE）。

## Scope 范围（可选）

放在括号内，表示影响的模块。**小写，多词用连字符连接**：

```
feat(parser): add array parsing support
fix(api-client): handle timeout errors
```

## Description 描述（必须）

- 现在时态、祈使句：`add` 而非 `added` / `adds`
- 首字母小写，结尾不加句号
- ≤ 72 字符（建议 ≤ 50 更佳）
- 用动词开头，简短说明做了什么

## Body 正文（可选）

- 空一行后开始
- 说明"做了什么"和"为什么"（diff 已展示 what，正文补 why）
- 每行 ≤ 72 字符，可多行，可用列表

## Footer 脚注（可选）

- 空一行后开始
- 格式：`<token>: <value>` 或 `<token> #<value>`
- 每个脚注独占一行

### 破坏性变更

两种方式表示（对应 SemVer **MAJOR**）：

**方式 1：`!` 在 type 后**
```
feat!: remove deprecated API endpoints
feat(api)!: change authentication flow
```

**方式 2：BREAKING CHANGE 脚注**
```
feat: add new config format

BREAKING CHANGE: config file format changed from YAML to JSON
```

### 关联 Issue

```
fix: resolve login timeout

Closes #123
Refs #456
```

## GOOD vs BAD 对比

### 简单提交

✅ `feat: add user authentication`
❌ `added user authentication`（过去时、无 type）

### 带范围

✅ `feat(auth): add OAuth2 login support`
❌ `feat: added OAuth2 to auth`（无 scope、过去时）

### 带正文

✅
```
feat: add user profile management

Add functionality for users to:
- Update profile information
- Change password
- Upload avatar image
```

❌ `feat: add profile` + 一句话流水账

### 破坏性变更

✅
```
feat!: remove deprecated API endpoints

BREAKING CHANGE: The following endpoints have been removed:
- /api/v1/users
- /api/v1/posts

Use /api/v2/* endpoints instead.
```

❌ `feat: remove old endpoints`（未标记破坏性）

### 关联 Issue

✅
```
fix: resolve authentication timeout issue

Closes #123
Refs #456
```

❌ `fix: auth issue` + `#123`（标题模糊、issue 未用 footer）

## 常见错误

| 错误 | 正确 |
|------|------|
| `feat: Added feature` | `feat: add feature`（现在时态、小写） |
| `fix: fix bug.` | `fix: resolve null pointer exception`（具体、无句号） |
| `FEAT: new feature` | `feat: new feature`（type 小写） |
| `feat add feature` | `feat: add feature`（冒号后有空格） |
| `feat(scope)add feature` | `feat(scope): add feature`（冒号后有空格） |
| `feat(UserService): ...` | `feat(user-service): ...`（scope 小写、连字符） |

## 最佳实践

- **一个提交一个逻辑变更**——原子性优于体量
- **标题清晰具体**——"add search with debouncing" 胜于 "improve search"
- **正文说"为什么"而非"做了什么"**——diff 已展示 what，正文补 why
- **关联 Issue**——`Closes #123` 让 PR 自动关闭 issue
- **不混合格式化与逻辑**——`style:` 和 `feat:` 分开提交
- **不提交调试代码或临时文件**

## 快速参考

| 场景 | Type | 示例 |
|------|------|------|
| 新功能 | `feat` | `feat: add user dashboard` |
| 修复 Bug | `fix` | `fix: resolve login error` |
| 更新文档 | `docs` | `docs: update API reference` |
| 代码格式 | `style` | `style: format with prettier` |
| 重构代码 | `refactor` | `refactor: simplify validation` |
| 性能优化 | `perf` | `perf: cache database queries` |
| 添加测试 | `test` | `test: add integration tests` |
| 构建更改 | `build` | `build: upgrade dependencies` |
| CI 配置 | `ci` | `ci: add GitHub Actions` |
| 维护任务 | `chore` | `chore: update license` |
| 回退提交 | `revert` | `revert: feat(api-key)` |

## 工具推荐

- **commitlint** - 校验 commit 格式
- **commitizen** - 交互式 commit 辅助
- **semantic-release** - 自动版本发布

## 参考链接

- [Conventional Commits Specification v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [Angular Commit Guidelines](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#commit)

## macOS 复制到剪贴板

在 macOS 系统下生成 commit message 后，使用 `pbcopy` 将其复制到系统剪贴板，便于直接粘贴到 git GUI 或终端。

**检测系统：**

```bash
[[ "$(uname)" == "Darwin" ]] && echo "macOS"
```

**单行消息：**

```bash
echo -n "feat(parser): add array parsing support" | pbcopy
```

**多行消息（含 body / footer）：**

```bash
pbcopy <<'EOF'
fix: prevent request race condition

Introduce request ID to track concurrent requests.
Reject duplicate requests with same ID.

Refs: #123
EOF
```

**Agent 工作流建议：**

生成 commit message 后，若检测到 `uname` 输出为 `Darwin`，自动通过 `pbcopy` 复制结果，并在回复中提示「已复制到剪贴板」。非 macOS 系统跳过此步骤。
