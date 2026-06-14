---
name: tmux
description: 以脚本方式驱动 tmux：创建后台会话、用 send-keys 向运行中的程序发命令、用 capture-pane 读输出。用于自动化 REPL/SSH/调试器、并发跑多个长生命周期服务、跨调用保持 shell 状态、或让用户 attach 到自动化现场——普通 Bash 拿不到 PTY 时使用。
---

# tmux 自动化技能

本技能教 Claude 如何用 tmux 在自动化场景里**驱动交互式程序**。重点不是手按键绑定，而是用 `tmux` 子命令以脚本方式创建会话、发命令、读输出。

## 心智模型

```
程序  ⊂  面板 (pane, %X)  ⊂  窗口 (window, @X)  ⊂  会话 (session, $X)  ⊂  客户端
```

- 一个**面板**里跑一个程序，提供完整 PTY。
- **窗口**是一组面板的容器，占满终端。
- **会话**是一组窗口，可被多个客户端 attach 共享。
- **服务器**进程在后台维护所有状态；只要服务器没被 kill，会话就一直在。

每种对象都有稳定的**唯一 ID**：会话 `$N`、窗口 `@N`、面板 `%N`。**永远用 ID 定位**——索引 (`0`、`1.2`) 在窗口被创建/关闭时会变，ID 不会。

---

## 何时该用本技能

满足下列任一条即可：

1. 要向已经启动的程序**发命令**（python REPL、psql、gdb、ssh 远端 shell、claude/codex CLI 等）。普通 Bash 启动后无法再向 stdin 投递输入，tmux 可以。
2. 程序拒绝在非 TTY 下工作，或在管道里行为变差（丢色、不刷新、缓冲变怪、curses 错乱）。tmux 提供真 PTY。
3. 需要**多个并发长生命周期服务**，且要分别向它们发命令、分别读输出（前端 dev、后端、worker、日志监控）。
4. 想让**用户随时 attach** 看 Claude 当前操作的现场，或在 Claude 离开后接管。
5. 需要在**跨多次 Claude 工具调用之间保留**同一个 shell/程序的状态（环境变量、cd 后的目录、virtualenv、登录的 ssh 连接）。

不满足以上任何一条时，普通的 Bash 调用就够了，没必要套 tmux。

---

## 黄金法则

**永远先抓 ID，再用 ID 操作。** 创建任何对象时都加 `-d -P -F '#{...}'`，把 stdout 拿到的 ID 存进 shell 变量，后续命令一律用 `-t $ID`。

```bash
# 幂等防御：同名会话已存在则先清掉，避免 new-session 失败
tmux has-session -t '=claude-work' 2>/dev/null && tmux kill-session -t '=claude-work'

# -d 不 attach；-P 打印目标；-F 指定打印格式
S=$(tmux new-session -d -P -F '#{session_id}' -s claude-work)
W=$(tmux new-window  -d -P -F '#{window_id}'  -t "$S")
P=$(tmux split-window -d -P -F '#{pane_id}'   -t "$W")
```

这之后 `$S`、`$W`、`$P` 是稳定句柄，重命名/重排都不影响。`-t '=name'` 的 `=` 前缀强制精确匹配，避免误命中名字相近的别的会话。

---

## 五个核心模板

### 模板 1：创建一个后台会话，跑一个程序

```bash
# 创建会话，在第一个面板里启动 python，并拿到面板 ID
PANE=$(tmux new-session -d -s repl -P -F '#{pane_id}' 'python3 -i')
```

`-i` 是给 python 的：让它启动后进入 REPL 而不是执行完命令就退出（tmux 已经提供了真 PTY，所以 stdin 一定是 tty；`-i` 解决的是 python 的行为而非 tty 检测）。

> 本节模板为简化起见省略了 `has-session` 幂等检查。脚本要可重复运行时，按"黄金法则"那段代码先做 `has-session && kill-session` 清理，或改用 `tmux new-session -A -d ...`（已存在则复用、不存在才建）。

### 模板 2：向运行中的程序发命令

```bash
tmux send-keys -t "$PANE" 'import os; print(os.getcwd())' Enter
```

- 解析按**位置参数为单位**：每个独立参数先整体匹配键名（`Enter`、`Tab`、`C-c`、`F1` 等），匹配上就发那个键的转义序列；匹配不上就把**整个参数作为字面字符串逐字符发送**。注意：不会把"参数里的某些子串"再去匹配键名——`'cmd Enter'` 是六个字符（c, m, d, 空格, E...）一起发，不会触发回车。
- 因此**命令文本和回车要分成两个参数**：`'cmd' Enter`，不要写成 `'cmd\n'` 或 `'cmd Enter'`。
- 要发的字面量恰好等于某个键名（比如真要键入 "Enter" 这个词），加 `-l` 关闭键名识别：`tmux send-keys -lt "$PANE" 'Enter'`。
- 取消正在跑的程序：`tmux send-keys -t "$PANE" C-c`。

### 模板 3：读取面板输出

```bash
# 读当前可见内容（包含已滚出屏幕之前的最后一屏）
tmux capture-pane -p -t "$PANE"

# 读完整历史（含 scrollback）
tmux capture-pane -p -t "$PANE" -S -

# 保留尾随空格 + 重新拼接折行（适合解析结构化输出）
tmux capture-pane -p -t "$PANE" -S - -J
```

`-p` 表示 print 到 stdout（不加 `-p` 则存到 paste buffer）。`-S` 是起始行，`-` 表示历史最早一行；`-E` 是结束行，默认到可见区末尾。

### 模板 4：发命令后等程序就绪

程序处理输入需要时间，盲目立刻 capture 容易拿到旧画面。轮询 capture 直到看到稳定的提示符：

```bash
tmux send-keys -t "$PANE" 'long_running_thing()' Enter

ok=0
for _ in $(seq 1 30); do
  # 范围设大一点：覆盖命令本身的输出加上提示符所在行
  out=$(tmux capture-pane -p -t "$PANE" -S -200 -J)
  # 用两个分支匹配提示符：
  #   1) "<换行>>>>" — 提示符前有更早的输出（绝大多数情况）
  #   2) ">>>"      — 极少数边界：捕获区起点恰好就是提示符所在行（无前导换行）
  # 不依赖提示符末尾的尾随空格——不同环境（python "> "、shell "$ "）习惯不同，
  # 而且 capture 在不带 -J/-N 时会吃掉它们。
  case $out in
    *"
>>>"*|">>>"*) ok=1; break ;;
  esac
  sleep 1
done

if [ "$ok" -ne 1 ]; then
  echo "timeout waiting for prompt; last capture:" >&2
  echo "$out" >&2
  exit 1
fi
echo "$out"
```

要点：

- 在 send-keys 后**不要不 sleep 直接 capture**，至少留一个轮询循环；用面板里独有的提示符当结束信号，比"等固定秒数"可靠得多。
- `case` 模式里嵌入的是**真实换行符**（双引号内回车换行），不是 `\n` 转义——后者在 case 里会被当成两个字符 `\` 和 `n`。"换行+提示符"模式锁定的是"提示符出现在某行行首"，避免误匹配字符串里偶然出现的 `>>>`；附加 `">>>"*` 兜底新会话刚启动、捕获区第一行就是提示符的边界情况。
- **永远显式判定超时**，不要让脚本在没看到提示符时静默继续。
- `-J` 同时拼接折行并保留尾随空格——长命令被终端宽度切断时仍能正确解析。

### 模板 5：并发跑多个服务

```bash
S=$(tmux new-session -d -s services -P -F '#{session_id}')

# 第一个面板/窗口已经存在但 new-session 没 -P 出来——单独取 ID
W0=$(tmux display -p -t "$S" -F '#{window_id}')
BACKEND=$(tmux display -p -t "$W0" -F '#{pane_id}')
tmux rename-window -t "$W0" services
tmux send-keys -t "$BACKEND" 'cd backend && npm run dev' Enter

# 再起一个窗口跑前端
FRONTEND=$(tmux new-window -d -P -F '#{pane_id}' -t "$S" -n frontend)
tmux send-keys -t "$FRONTEND" 'cd frontend && npm run dev' Enter

# 同窗口里再分一个面板跑日志
LOGS=$(tmux split-window -d -P -F '#{pane_id}' -t "$FRONTEND")
tmux send-keys -t "$LOGS" 'tail -F /tmp/app.log' Enter
```

之后任何时候都能用 `$BACKEND` / `$FRONTEND` / `$LOGS` 各自发命令、各自 capture。所有定位均用 ID，与黄金法则一致。

### 让用户接管 / Claude 离开

- 用户想看：让 Ta 跑 `tmux attach -t =services`（`=` 前缀强制精确匹配，避免被名字相近的别的会话抢去）。`-d` 选项可顺便把其他客户端踢掉以避免大小冲突。
- Claude 不能在自己的工具调用里 attach（会卡住前台），但可以在创建会话时**不 attach**，让会话留在后台供用户 attach。
- 完事清理：`tmux kill-session -t =services`。一个孤立的会话不会自己消失。

---

## 关键陷阱（自动化场景最常翻车的几个）

1. **send-keys 不带 Enter 等于没按回车。** 几乎所有"命令发了但没反应"都是这个。检查最后一个参数是不是 `Enter`。
2. **键名 vs 字面量的歧义。** 要发的字符串里如果有 `Enter`、`Tab`、`Space` 这种英文单词，加 `-l` 强制字面量，否则会被当成按键。引号里的特殊 shell 字符（`$`、反引号）也要按 shell 规则转义。
3. **capture 时机。** 紧跟 send-keys 之后立即 capture 拿到的是发命令前的画面。永远轮询，用提示符或自定义 sentinel 行作为完成标志。
4. **窗口/面板索引会变。** 不要靠 `-t 0.1` 这种位置定位长期跑的脚本，用 `%pane_id`。
5. **嵌套 tmux**（在已经 attach 的 tmux 里再 attach 另一个）会让前缀键冲突。Claude 的脚本里发命令用绝对 `tmux ...` 不需要前缀键，所以这条只在让用户手动接管时关心——告诉用户**把外层前缀键连按两次**（默认是 `Ctrl-b Ctrl-b`，若用户改过就用他自己的 prefix 重复一次），就能把前缀传给内层。**更彻底的办法是 Claude 本来就用独立 socket** 启动会话（`tmux -L claude ...`），与用户的默认 socket 完全隔离，嵌套和前缀冲突都不存在；详见 `references/targets-and-ids.md` 的"嵌套"一节。
6. **TERM 必须是 tmux 兼容值。** 自动化里很少需要管，但若程序投诉 `unknown terminal`，在创建会话前 `export TERM=tmux-256color` 或 `screen-256color`。
7. **kill 不会问你。** `tmux kill-server` 会干掉所有会话，慎用；用 `kill-session -t $S` 只清自己的。
8. **进程退出后面板会消失，错误现场也丢了。** 默认 `remain-on-exit` 是 `off`，进程一旦 exit，pane 立刻关闭，再去 `capture-pane -t %P` 会拿到错误"can't find pane"。要保留崩溃现场用于事后取错信息，创建会话时打开此选项：
   ```bash
   tmux new-session -d -s claude-work \; \
        set-option -t claude-work remain-on-exit on
   # 之后 pane 内进程退出，面板保留并显示 "Pane is dead"，capture 仍可用
   ```

---

## 何时翻参考资料

`references/` 下按场景拆分。**不要预先全读**，需要时再开对应文件：

| 你正在做的事 | 打开 |
|---|---|
| 选 send-keys / capture-pane / pipe-pane 的某个细节 flag | `references/automation.md` |
| 拼 `-t` 目标（跨会话、相对位置、{last}/{up-of} 等） | `references/targets-and-ids.md` |
| 找一个完整可用的脚本模板（dev server 等待就绪、并发服务、REPL 自动化） | `references/recipes.md` |
| 排查 send-keys 没生效 / capture 总拿空 / TUI 显示乱码 | `references/pitfalls.md` |

---

## 参考来源

本技能的命令语法和示例基于本仓库的 tmux 官方 wiki 内容（特别是 `Advanced-Use.md` 的 "Sending keys"、"Capturing pane content"、"Targets" 与 "Targets for new panes, windows and sessions" 章节）以及 `Recipes.md`。如果对某条 flag 行为有疑问，回去查 `man tmux` 是最权威的途径。
