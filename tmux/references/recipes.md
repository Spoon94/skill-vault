# recipes.md — 实战脚本配方

每个配方都是一个完整、可直接 copy 调整的 shell 脚本。统一约定：

- 使用独立 socket `-L claude` 避免和用户其他 tmux 会话冲突。
- 创建后立刻把 ID 存进变量。
- 清理用 `kill-session -t "=name"` 精确匹配。

---

## 配方 1：等一个 dev server 就绪后再继续

场景：跑 `npm run dev`，等到 "ready in" 出现再开始 e2e 测试。

```bash
SESSION=dev
SOCKET=claude

tmux -L "$SOCKET" has-session -t "=$SESSION" 2>/dev/null && \
  tmux -L "$SOCKET" kill-session -t "=$SESSION"

P=$(tmux -L "$SOCKET" new-session -d -s "$SESSION" -P -F '#{pane_id}' \
      'cd /path/to/app && npm run dev 2>&1')

# 轮询面板内容，看到就绪标志就退
deadline=$(( $(date +%s) + 120 ))      # 最多等 2 分钟
while :; do
  out=$(tmux -L "$SOCKET" capture-pane -p -t "$P" -S -200 -J)
  case $out in
    *"ready in"*|*"Local:"*) break ;;
  esac
  if [ "$(date +%s)" -gt "$deadline" ]; then
    echo "timeout waiting for dev server" >&2
    echo "--- last 50 lines ---" >&2
    echo "$out" | tail -50 >&2
    exit 1
  fi
  sleep 1
done

echo "server ready, pane=$P"
# 之后用 $P 继续操作；测试结束统一 kill-session
```

要点：

- `2>&1` 把 stderr 也吸到 stdout，否则 capture 看不到错误。
- `case` 语句的多模式 `*"a"*|*"b"*` 比 `grep` 更适合 shell 内嵌（无子进程）。
- 设上限的 deadline 是必须的：服务器可能根本起不来，循环要能自己退出。

---

## 配方 2：自动化 Python REPL 与读结果

场景：起一个 python 解释器，发几条命令，按段拿到每次输出。

```bash
SOCKET=claude
SESSION=repl

tmux -L "$SOCKET" kill-session -t "=$SESSION" 2>/dev/null
P=$(tmux -L "$SOCKET" new-session -d -s "$SESSION" -P -F '#{pane_id}' 'python3 -i -q')

# 等首个提示符
sleep 0.3
while ! tmux -L "$SOCKET" capture-pane -p -t "$P" -S -200 -J | grep -q '^>>> '; do
  sleep 0.1
done

# 用 sentinel 行标记每段输出的边界
send_and_read() {
  local cmd=$1
  local sentinel="__DONE_$RANDOM__"
  tmux -L "$SOCKET" send-keys -t "$P" "$cmd" Enter
  tmux -L "$SOCKET" send-keys -t "$P" "print('$sentinel')" Enter
  while ! tmux -L "$SOCKET" capture-pane -p -t "$P" -S -200 -J | grep -q "$sentinel"; do
    sleep 0.1
  done
  # 拿出这段的输出（sentinel 之前那块）
  # 注意：下面 awk 把 $cmd 拼进了正则；如果命令含 / . * [ ] 等正则元字符或 / 分隔符
  # 会出错。生产代码里改用 -v c="$cmd" 传变量并用 index($0,c) 做字面包含匹配更安全。
  tmux -L "$SOCKET" capture-pane -p -t "$P" -S - -J | \
    awk -v s="$sentinel" 'BEGIN{p=0} /__DONE_/{exit} p; />>> '"$cmd"'/{p=1}'
}

send_and_read "import os"
send_and_read "os.getcwd()"

tmux -L "$SOCKET" kill-session -t "=$SESSION"
```

要点：

- **sentinel 模式**比"等 N 秒"或"等下一个 `>>>`"健壮——长任务、多行输出、未知耗时都能正确切段。
- 每次 sentinel 用 `$RANDOM` 避免历史里有一样的字符串误判。
- python 用 `-q` 抑制版本横幅，输出更干净。

---

## 配方 3：并发跑前后端 + 日志面板

场景：一个会话三个面板，前端、后端、日志各占一个；后续可分别发命令、分别 capture。

```bash
SOCKET=claude
SESSION=app

tmux -L "$SOCKET" kill-session -t "=$SESSION" 2>/dev/null

# 创建会话和第一个面板（后端）
S=$(tmux -L "$SOCKET" new-session -d -s "$SESSION" -P -F '#{session_id}' -n services)
W=$(tmux -L "$SOCKET" display -p -t "$S" -F '#{window_id}')
BE=$(tmux -L "$SOCKET" display -p -t "$W" -F '#{pane_id}')
tmux -L "$SOCKET" send-keys -t "$BE" 'cd backend && npm run start' Enter

# 横向劈一个跑前端
FE=$(tmux -L "$SOCKET" split-window -d -h -t "$BE" -P -F '#{pane_id}')
tmux -L "$SOCKET" send-keys -t "$FE" 'cd frontend && npm run dev' Enter

# 把前端那块再纵向劈一个跑日志
LOG=$(tmux -L "$SOCKET" split-window -d -v -t "$FE" -P -F '#{pane_id}' \
        'tail -F /tmp/app.log')

# 把句柄存到环境文件，后续步骤里 source
cat >/tmp/$SESSION.env <<EOF
SOCKET=$SOCKET
SESSION=$SESSION
BE=$BE
FE=$FE
LOG=$LOG
EOF

echo "started: BE=$BE FE=$FE LOG=$LOG"
```

后续 Claude 调用里：

```bash
. /tmp/app.env
# 重启后端
tmux -L "$SOCKET" send-keys -t "$BE" C-c
sleep 0.5
tmux -L "$SOCKET" send-keys -t "$BE" 'npm run start' Enter
```

要点：

- ID 写到文件持久化，跨工具调用复用。
- `-h` / `-v` 决定分割方向：`-h` 是 horizontal（左右），`-v` 是 vertical（上下）。
- 第三个面板直接传命令字符串作为最后一个位置参数，比 `send-keys 'tail ...' Enter` 简洁。

---

## 配方 4：让一个程序的全部输出持久落到文件

```bash
SOCKET=claude
P=$(tmux -L "$SOCKET" new-session -d -s capture -P -F '#{pane_id}' 'long-running-thing')
tmux -L "$SOCKET" pipe-pane -t "$P" "cat >> /tmp/capture.log"

# 后续随时增量读
tail -n 0 -f /tmp/capture.log &
```

`pipe-pane` 比反复 `capture-pane -S - -E -` 轻量得多，且不会丢任何字节（capture 受限于 history-limit）。需要更大 scrollback 时才考虑改 `set -g history-limit 50000`。

---

## 配方 5：通过 SSH 跑命令并保留连接

场景：每次新 SSH 慢，希望开一次会话，后续命令复用同一连接。

```bash
SOCKET=claude
SESSION=remote
HOST=user@server

tmux -L "$SOCKET" kill-session -t "=$SESSION" 2>/dev/null
P=$(tmux -L "$SOCKET" new-session -d -s "$SESSION" -P -F '#{pane_id}' "ssh $HOST")

# 等远端提示符
while ! tmux -L "$SOCKET" capture-pane -p -t "$P" -S -200 -J | grep -qE '\$ $|# $'; do
  sleep 0.2
done

run_remote() {
  tmux -L "$SOCKET" send-keys -t "$P" "$1" Enter
  sleep 0.1
  tmux -L "$SOCKET" capture-pane -p -t "$P" -S -200 -J
}

run_remote 'hostname'
run_remote 'df -h /'
```

也可以让 OpenSSH 自己做连接复用（`ControlMaster auto`），但 tmux 方案有个独特好处：**整段 session 还能让用户 attach 进来观察或接管**。

---

## 配方 6：交互式 CLI（codex、claude、aider 等）

许多 AI/REPL CLI 用 readline 或 raw mode，必须真 PTY。tmux 是最简单的容器。

```bash
SOCKET=claude
P=$(tmux -L "$SOCKET" new-session -d -s assistant -P -F '#{pane_id}' 'codex')

# 给个长 prompt
PROMPT='请阅读 ./README.md 并总结主要功能'
tmux -L "$SOCKET" send-keys -t "$P" "$PROMPT" Enter

# 等 codex 写完。它通常以一个空提示符行收尾——选一个稳定 sentinel
deadline=$(( $(date +%s) + 300 ))
while :; do
  out=$(tmux -L "$SOCKET" capture-pane -p -t "$P" -S -500 -J)
  # codex 完成后会再次显示 ">" 或 "User:" 一类的输入提示
  case $out in
    *"User:"*"User:"*) break ;;
  esac
  [ "$(date +%s)" -gt "$deadline" ] && { echo "timeout"; break; }
  sleep 2
done

echo "$out" | tail -100
```

挑 sentinel 时观察该 CLI 真实输出几次再写脚本，每个 CLI 不一样。

---

## 配方 7：让用户接管（移交现场）

```bash
SESSION=claude-work
SOCKET=claude

# 已经存在
echo "用户可以用以下命令 attach 看现场："
echo "  tmux -L $SOCKET attach -t =$SESSION"
echo "在 tmux 里按 Ctrl-b d 即可分离回到 shell（不会杀掉会话）"
```

如果用户已经在自己的 tmux 里，提示 Ta 用 `TMUX= tmux -L claude attach -t =claude-work`。

---

## 配方 8：把脚本设计成幂等可重入

Claude 多次调用同一个 setup 脚本时不应每次重新启服务，浪费时间也容易冲突。

```bash
SOCKET=claude
SESSION=app

if tmux -L "$SOCKET" has-session -t "=$SESSION" 2>/dev/null; then
  echo "reusing existing session"
else
  echo "creating fresh session"
  tmux -L "$SOCKET" new-session -d -s "$SESSION" -n main
  # 首次创建时按窗口名定位还是安全的（刚建出来名字就是 main）
  W=$(tmux -L "$SOCKET" display -p -t "=$SESSION:main" -F '#{window_id}')
  tmux -L "$SOCKET" send-keys -t "$W" 'npm run dev' Enter
  # ... 等就绪 ...
fi

# 复用已有会话时窗口可能已被用户重命名，所以靠"会话里的当前活动窗口"来锚定，
# 再展开成稳定的 window_id 和 pane_id 后续使用
W=$(tmux -L "$SOCKET" display -p -t "=$SESSION" -F '#{window_id}')
P=$(tmux -L "$SOCKET" display -p -t "$W" -F '#{pane_id}')
```

---

## 通用清理函数

放在脚本顶部，trap 上：

```bash
SOCKET=claude
SESSION=app

cleanup() {
  tmux -L "$SOCKET" kill-session -t "=$SESSION" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
```

只在脚本"自己拥有"该会话时这么做。Claude 跨调用复用会话时**不要**装 trap，会话需要在脚本退出后还活着。
