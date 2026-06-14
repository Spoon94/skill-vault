# targets-and-ids.md — 目标语法与 ID 管理

tmux 命令几乎都接受 `-t target`。在自动化里目标错位是头号 bug 来源。本文件整理可靠的写法。

---

## 三种唯一 ID

| 对象 | ID 形式 | 例 |
|---|---|---|
| 会话 (session) | `$N` | `$0`、`$3` |
| 窗口 (window)  | `@N` | `@1`、`@42` |
| 面板 (pane)    | `%N` | `%0`、`%17` |

ID 在 tmux 服务器进程的整个生命周期里**只递增、不复用**：被 kill 的会话/窗口/面板，它的 ID 永远不会再被分配给新对象。这就是它适合做长期句柄的原因。

查所有 ID：

```bash
tmux list-sessions -F '#{session_id} #{session_name}'
tmux list-windows  -a -F '#{session_id}:#{window_id} #{window_name}'
tmux list-panes    -a -F '#{session_id}:#{window_id}.#{pane_id} #{pane_current_command}'
```

`-a` 表示跨所有会话/窗口列出。

---

## target 的写法

完整形式是 `session:window.pane`，每段都可省略：

```
-t $0:@1.%2     # 会话 $0 的窗口 @1 的面板 %2
-t %2           # 直接指面板 %2，会话/窗口 tmux 自己反推
-t $0:1         # 会话 $0 的窗口索引 1（注意：索引会变）
-t mysession    # 名字前缀匹配；=mysession 表示精确匹配
```

### 各段允许的写法

**session 段**：

| 写法 | 含义 |
|---|---|
| `$N`           | 会话 ID（最稳） |
| `=name`        | 精确名字匹配 |
| `name`         | 前缀匹配，可能匹到多个里的第一个 |
| `f*` / `f?`    | 通配模式 |

**window 段**：

| 写法 | 含义 |
|---|---|
| `@N`           | 窗口 ID（最稳） |
| `0`、`1`...    | 索引 |
| `{start}` 或 `^` | 索引最小的窗口 |
| `{end}`   或 `$` | 索引最大的窗口 |
| `{last}`  或 `!` | 上一个活动窗口 |
| `{next}`  或 `+` | 下一个 |
| `{previous}` 或 `-` | 上一个（按顺序） |
| `name`         | 名字前缀 |

**pane 段**：

| 写法 | 含义 |
|---|---|
| `%N`              | 面板 ID（最稳） |
| `0`、`1`...       | 索引 |
| `{last}` 或 `!`   | 上一个活动面板 |
| `{next}` `{previous}` | 顺序里的下一个/上一个 |
| `{top}` `{bottom}` `{left}` `{right}` | 位置 |
| `{top-left}` `{top-right}` `{bottom-left}` `{bottom-right}` | 角 |
| `{up-of}` `{down-of}` `{left-of}` `{right-of}` | 相对当前活动面板的方位 |

---

## 自动化最佳实践：始终用 ID

```
不要：  tmux send-keys -t mywin:0.1 'cmd' Enter
要：    tmux send-keys -t %17 'cmd' Enter
```

原因：

1. 索引随窗口/面板的创建和关闭而变。tmux 内部规则会在某些命令后让"`-t1`"突然指向不同对象（仓库 wiki 例子：`splitw -d` 之后窗口 `@1` 变成 `@8`）。
2. 名字前缀匹配可能有歧义（多个会话名字都以 `dev` 开头）。
3. ID 简短稳定，写脚本一目了然。

---

## 创建对象时一次性拿到 ID：`-d -P -F`

三个 flag 是自动化里最重要的"组合拳"：

- `-d`：**don't attach**。不让客户端跳进新对象，命令立即返回，是脚本能继续的前提。
- `-P`：**print** 新对象的目标到 stdout。
- `-F format`：自定义打印格式，配合命令替换捕获。

```bash
S=$(tmux new-session  -d -s claude -P -F '#{session_id}')
W=$(tmux new-window   -d -t "$S"  -P -F '#{window_id}')
P=$(tmux split-window -d -t "$W"  -P -F '#{pane_id}')

echo "session=$S window=$W pane=$P"
# session=$3 window=@7 pane=%12
```

不带 `-F` 时 `-P` 也会打印某种默认格式（如 `2:`），但格式不稳定难解析。**永远显式指定 `-F`**。

### 一行起多个面板并各自存 ID

```bash
S=$(tmux new -d -s app -P -F '#{session_id}')
P0=$(tmux display -p -t "$S" -F '#{pane_id}')              # 第一个面板已存在
P1=$(tmux split-window -d -t "$P0" -P -F '#{pane_id}' -h)
P2=$(tmux split-window -d -t "$P1" -P -F '#{pane_id}' -v)
```

`split-window -h` 是水平分（左右）、`-v` 是垂直分（上下）。`new-session` 第一个面板**不会**通过 `-P` 返回——单独用 `display -p` 取它的 ID。

---

## 用格式取面板状态

`#{...}` 格式变量可以查询关于 pane/window/session 的几乎所有信息，配合 `display-message -p` / `list-* -F` 一起用：

```bash
# 这个面板里在跑什么命令？
tmux display -p -t "$P" -F '#{pane_current_command}'

# 当前工作目录？
tmux display -p -t "$P" -F '#{pane_current_path}'

# 这个面板还活着吗？(死了的面板会从 list 里消失)
tmux list-panes -t "$P" -F '#{pane_id}' 2>/dev/null | grep -q "$P" && echo alive || echo dead

# 所有面板里在跑 node 的：
tmux list-panes -a -F '#{pane_id} #{pane_current_command}' | awk '$2=="node"'
```

常用变量速记：`#{session_name}`、`#{session_id}`、`#{window_index}`、`#{window_name}`、`#{window_id}`、`#{pane_index}`、`#{pane_id}`、`#{pane_pid}`、`#{pane_current_command}`、`#{pane_current_path}`、`#{pane_dead}`、`#{pane_width}`、`#{pane_height}`。完整列表见 `Formats.md`。

---

## kill / 清理

```bash
tmux kill-pane    -t "$P"   # 关一个面板（窗口里其他面板还在）
tmux kill-window  -t "$W"   # 关一个窗口（含里面所有面板）
tmux kill-session -t "$S"   # 关整个会话
tmux kill-server            # 全杀，慎用——会干掉用户其他会话
```

清理脚本套路：

```bash
SESSION=claude-work
tmux has-session -t "=$SESSION" 2>/dev/null && tmux kill-session -t "=$SESSION"
```

`=` 前缀确保精确匹配，避免误杀名字相似的会话。

---

## 检查会话/服务器是否在

```bash
# 服务器是否在跑（任何会话存在即在）
tmux ls 2>/dev/null && echo "server up" || echo "no server"

# 特定会话是否存在
tmux has-session -t "=claude-work" 2>/dev/null && echo "exists"

# "存在则 attach 否则创建"
tmux new-session -A -s claude-work
```

`new-session -A` 在脚本入口很有用：幂等，第一次创建、之后直接 attach。但 `-A` 会 attach，**Claude 自己用要配合 `-d`**：

```bash
tmux new-session -A -d -s claude-work
```

---

## 嵌套（用户已经在 tmux 里）

如果用户的终端已经在一个 tmux 客户端里，再跑 `tmux attach` 默认会**拒绝**，因为嵌套会让前缀键混乱。两条路：

```bash
# 1. 显式允许（适合"我就是想嵌套"）
TMUX= tmux attach -t =claude-work    # 清空 $TMUX 让 tmux 不知道自己在嵌套

# 2. 用一个独立 socket，这样新服务器和外层完全无关
tmux -L claude attach -t =claude-work
```

`-L name` 切换 socket 名字（默认是 `default`）；`-S path` 指定 socket 完整路径。Claude 给用户的会话和系统其他 tmux 会话**用独立 socket** 是个好习惯，能避免互相干扰：

```bash
tmux -L claude new-session -d -s work
```

之后所有相关命令都加 `-L claude`。
