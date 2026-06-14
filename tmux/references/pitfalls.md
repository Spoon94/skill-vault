# pitfalls.md — 自动化场景常见问题诊断

按"症状 → 可能原因 → 排查/修复"组织。Claude 在自动化里翻车时按本表对照。

---

## 1. send-keys 看起来"没生效"

### 症状
`tmux send-keys -t %P 'cmd' Enter` 返回 0，但 `capture-pane` 里看不到命令运行结果。

### 排查清单

1. **真的发了 Enter 吗？** 漏掉 `Enter` 是头号原因。命令文本进了输入行但没回车，自然不执行。检查最后一个参数。

2. **目标 ID 还有效吗？** 程序退出后面板可能已 dead，新面板用了新 ID。
   ```bash
   tmux list-panes -a -F '#{pane_id} #{pane_dead} #{pane_current_command}' | grep '%P'
   ```
   `pane_dead=1` 或者列表里根本没有就是没了。

3. **面板里跑的是 raw mode 程序？** vim、less、TUI 程序会拦截按键，普通字符串作为编辑命令而非"输入"。要往 vim 发文字，先 `i` 进插入模式，或者用 `:!cmd` 这类显式入口。

4. **shell 里有未结束的引号或反斜杠？** 上一个 send-keys 留下了未闭合的 `"`，下一条命令被当成上条的延续。先发 `C-c` 复位：
   ```bash
   tmux send-keys -t "$P" C-c
   sleep 0.2
   ```

5. **被解释成了键名？** 想发字面量 `Enter`、`Tab` 这些字时必须 `-l`。

---

## 2. capture-pane 拿不到刚发的命令的输出

### 症状
send-keys 之后立刻 capture，输出里只有命令前的内容，看不到结果。

### 原因
send-keys 是异步的。tmux 把按键放进面板的输入队列就立刻返回了，程序还没来得及处理。

### 修复
**轮询直到看到完成标志。** 不要 `sleep 1` 完事，因为：

- 命令快时浪费时间；
- 命令慢时仍可能没结束。

正确做法见 SKILL.md 的"模板 4"：用提示符或 sentinel 行做完成判定。

---

## 3. capture 出来的中文/长行被截成两半

### 症状
JSON 解析失败、表格列错位、URL 中间断开。

### 原因
tmux 按面板宽度折行，`capture-pane` 默认按显示行抓，长行被物理切开。

### 修复
**永远加 `-J`**，把折行重新拼回逻辑行：

```bash
tmux capture-pane -p -t "$P" -S -200 -J
```

如果还涉及尾随空格对齐，再加 `-N`。

---

## 4. 程序投诉 "Inappropriate ioctl" / "not a tty"

### 症状
某些程序在 tmux 内仍报错，但在普通终端里正常。

### 可能原因

- 在 send-keys 时用了管道把命令 piped 进去（如 `echo cmd | tmux send-keys ...` 这种误用），打破了 PTY。其实 send-keys 不需要管道。
- 程序自己 fork 出新进程时把 stdin 改成了 `/dev/null`。这是程序的问题，不是 tmux 的。

### 修复
确认 send-keys 调用形式是位置参数而非管道：`tmux send-keys -t %P 'cmd' Enter`。

---

## 5. 颜色/边框/Unicode 显示乱

### 症状
- 终端字符画拼不上（tmux 自己的边框是虚线或断开）。
- TUI 程序颜色全错。
- `claude` / `vim` 显示 `[?2004h` 等转义码原文。

### 原因
内层 `TERM` 设错。tmux 启动后会把面板里的 `TERM` 设成 `screen` 或 `tmux-256color`（取决于 `default-terminal` 选项）；如果系统里没装该 terminfo 条目，应用就拿不到颜色能力。

### 修复

```bash
# 先确认 terminfo 装了
infocmp tmux-256color >/dev/null 2>&1 && echo OK || echo "missing terminfo"

# 没有的话，最简单的办法是退到 screen-256color
tmux set -g default-terminal screen-256color  # 写入配置
# 或临时
TERM=screen-256color
```

要更激进的真彩色：

```tmux
# tmux 3.2+
set -as terminal-features ',xterm*:RGB'
# 老版本
set -as terminal-overrides ',xterm*:Tc'
```

---

## 6. Escape 键延迟（vim、emacs 在 tmux 里反应慢）

### 症状
按 Esc 后 tmux 等 0.5s 才放行，vim 退出插入模式有可见延迟。

### 原因
tmux 默认 `escape-time 500`，等待是否有跟在 Esc 后的转义序列（如 Alt-key）。

### 修复

```tmux
set -s escape-time 10
```

设 0 在某些慢网络上会让 Alt-x 等组合误判，10ms 是稳妥折中。

---

## 7. attach 之后窗口/面板尺寸异常

### 症状
attach 后看到内容只占终端的一小块，或者出现一行 `.` 占位。

### 原因
**多个客户端 attach 同一会话且终端尺寸不同**时，tmux 默认把会话尺寸缩到最小客户端。`.` 是被裁掉部分的占位提示。

### 修复

```bash
# attach 时把其他客户端踢掉
tmux attach -d -t mysession

# 或全局策略改成"取最大"
tmux set -g window-size largest
```

Claude 自动化场景里基本不会触发，但用户接管时可能遇到。

---

## 8. 会话被意外清掉

### 症状
原本创建好的会话，下一次工具调用时 `has-session` 返回失败。

### 原因清单

1. **服务器整个被 kill**：用户手动 `tmux kill-server` 或重启电脑。
2. **socket 不一致**：第一次创建用了默认 socket，后续命令用了 `-L claude`，相当于在连不同服务器。
3. **会话名带特殊字符**：`-t name` 没用 `=` 前缀，前缀匹配命中了别的会话。

### 修复
- 始终用同一个 `-L socket-name`。
- `-t "=session"` 精确匹配。
- 关键脚本写成幂等：先 `has-session`，没有就重建。

---

## 9. pipe-pane 写文件越来越大

### 症状
`pipe-pane` 持续运行的会话，日志文件几小时长到 GB 级。

### 修复

- 用 `logrotate` 或 `multilog`。
- 用 `pipe-pane` 时不直接 `cat >>`，套一层只保最近 N 行：
  ```bash
  tmux pipe-pane -t "$P" 'tee -a /tmp/p.log >/dev/null && tail -c 5M /tmp/p.log >/tmp/p.log.tmp && mv /tmp/p.log.tmp /tmp/p.log'
  ```
  （这种过滤要小心 race，更稳是搭真 logrotate。）
- 只关心最近输出时直接 `capture-pane -S -200`，别开 pipe-pane。

---

## 10. 键名带修饰符不识别（C-/, S-Tab 等）

### 症状
`tmux send-keys -t %P S-Tab` 程序里没看到 Shift+Tab 效果。

### 原因
某些组合键的转义序列依赖于终端类型。客户端外层终端不发 "extended keys"，tmux 也无法 synthesize。

### 修复

```tmux
set -s extended-keys on
set -as terminal-features 'xterm*:extkeys'
```

并确认外层终端（iTerm2、Alacritty、Kitty）也开启了扩展键。

如果只是想取消 readline，发原始字节常常更可靠：

```bash
# Shift+Tab = ESC [ Z
tmux send-keys -t "$P" -H 1b 5b 5a
```

---

## 11. 想把命令 + 大量 stdin 一并送进面板

### 症状
要 `cat large_file | program` 但 `send-keys` 把整个文件一行行打字，慢且容易触发 readline 自动补全/历史。

### 修复
**让面板里的 shell 自己读文件**，而不是把内容一字一字打进去：

```bash
# 写到临时文件
cat > /tmp/payload <<'EOF'
... 大量内容 ...
EOF

tmux send-keys -t "$P" 'program < /tmp/payload' Enter
```

或者用 `pipe-pane -I` 把 stdin 直接喂面板（绕开按键解析）：

```bash
cat /tmp/payload | tmux pipe-pane -I -t "$P"
```

---

## 12. 脚本能跑但用户跑不动 / "tmux: command not found"

环境变量、PATH 在 SSH 非交互 shell 里和 Claude 运行环境不同。

修复：在脚本顶上写绝对路径或显式 source：

```bash
TMUX_BIN=/opt/homebrew/bin/tmux  # macOS
"$TMUX_BIN" new-session -d ...
```

也可以确认 `which tmux` 后写到环境变量里。

---

## 13. 进程一退出，面板就没了——错误信息也丢了

### 症状
跑一个会崩的程序，等 Claude 回头去 `capture-pane -t %P` 想看 traceback，命令报 `can't find pane: %P`。`list-panes -a` 里也看不到该 pane。

### 原因
`remain-on-exit` 默认是 `off`：面板里的进程一退出，tmux 立即销毁该 pane（最后一个 pane 退出时连带销毁 window 和 session）。capture 自然失败。

### 修复
在创建会话或窗口后立即开启该选项：

```bash
S=$(tmux new-session -d -s app -P -F '#{session_id}')
tmux set-option -t "$S" remain-on-exit on
# 也可以只对单个窗口设：tmux set-option -w -t "$W" remain-on-exit on

# 之后即使面板里的程序 exit，pane 还在，会显示 "Pane is dead (status N)"
# capture-pane -t %P 仍然能拿到崩溃前的全部输出
```

要重启该 pane 里的程序，用 `respawn-pane`：

```bash
tmux respawn-pane -t "$P" -k 'python3 -i'   # -k 强制覆盖已死的 pane
```

要彻底清掉死 pane：`tmux kill-pane -t "$P"`。

适合开 `remain-on-exit` 的场景：自动化里跑可能崩的程序、想保留事后诊断。不适合：长期常开的 dev server（一崩你看不到 pane 数变化，要靠 `pane_dead` 字段去查）。

---

## 备查：调试一个奇怪的 tmux 行为

```bash
tmux info                    # 服务器全局信息
tmux show -gv default-terminal
tmux list-panes -a -F '#{session_id} #{window_id} #{pane_id} #{pane_pid} #{pane_current_command} #{pane_dead}'
tmux source-file -v ~/.tmux.conf 2>&1   # 解析配置但不执行，验证语法
man tmux                     # 始终最权威
```
