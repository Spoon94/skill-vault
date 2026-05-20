---
name: conventional-commits
description: Use when writing Git commit messages, reviewing commits, or setting up commit message linting. Keywords: commit message, git commit, commitlint, semantic versioning, commit format.
---

# Conventional Commits

规范 Git 提交消息格式，便于自动化工具生成版本号、变更日志。

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

**其他类型允许**，但不影响语义版本（除非含 BREAKING CHANGE）。

## Scope 范围（可选）

放在括号内，表示影响的模块：

```
feat(parser): add array parsing support
fix(auth): resolve token expiration issue
```

## Description 描述（必须）

- 简短说明（建议 ≤ 50 字符）
- 使用动词、现在时态
- 结尾不加句号

## Body 正文（可选）

- 空一行后开始
- 说明"做了什么"和"为什么"
- 可多行

## Footer 脚注（可选）

- 空一行后开始
- 格式：`<token>: <value>` 或 `<token> #<value>`

### 破坏性变更

两种方式表示：

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

→ 对应 SemVer **MAJOR** 版本。

### 关联 Issue

```
fix: resolve login timeout

Closes #123
Refs #456
```

## 完整示例

**简单提交：**
```
docs: fix typo in README
```

**带范围：**
```
feat(lang): add Polish language support
```

**带正文和脚注：**
```
fix: prevent request race condition

Introduce request ID to track concurrent requests.
Reject duplicate requests with same ID.

Reviewed-by: John Doe
Refs: #123
```

**破坏性变更：**
```
feat!: change API response format

BREAKING CHANGE: response field `data` renamed to `payload`
```

## 常见错误

| 错误 | 正确 |
|------|------|
| `feat: Added feature` | `feat: add feature` |
| `fix: fix bug.` | `fix: resolve null pointer exception` |
| `FEAT: new feature` | `feat: new feature`（type 小写） |
| `feat add feature` | `feat: add feature`（冒号后有空格） |
| `feat(scope)add feature` | `feat(scope): add feature`（冒号后有空格） |

## 工具推荐

- **commitlint** - 校验 commit 格式
- **commitizen** - 交互式 commit 辅助
- **semantic-release** - 自动版本发布

## 参考链接

- [Conventional Commits Specification v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [Angular Commit Guidelines](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#commit)