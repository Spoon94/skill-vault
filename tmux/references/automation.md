# automation.md — send-keys / capture-pane / pipe-pane 详解

本文件覆盖 Claude 自动化 tmux 时使用频率最高的三个命令的所有相关 flag。其他 tmux 命令（`new-session`、`split-window`、`new-window`、`kill-session` 等）见 `targets-and-ids.md`。

---

## send-keys：把按键送进面板

### 基本形式

```
tmux send-keys -t <target> arg1 arg2 ...
```

每个独立位置参数会按下面顺序处理：

1. **键名匹配**：参数若是已知键名（`Enter`、`Tab`、`Space`、`BSpace`、`Escape`、`Up/Down/Left/Right`、`F1`...`F12`、`Home`、`End`、`PPage`、`NPage`、`IC`、`DC` 等），则发送该键的转义序列。
2. **修饰前缀**：键名前可加 `C-`（Ctrl）、`M-`（Meta/Alt）、`S-`（Shift）。例如 `C-c`、`M-x`、`C-M-l`。
3. **字面量回退**：匹配不上键名的参数被当作普通字符串，按字符依次发送。

### 关键 flag

- `-l`：**字面发送**，关闭键名识别。要发的字符串里恰好出现 `Enter`、`Tab` 这类英文单词时必须用，否则会被当成按键。

  ```bash
  tmux send-keys -lt "$P" 'Enter'   # 真的发 5 个字符 E-n-t-e-r
  tmux send-keys -t "$P" Enter      # 发回车
  ```

- `-R`：**重置终端状态**。屏幕变乱、ANSI 解析卡死时用，相当于"软复位"。

- `-N count`：把后面整组按键重复 `count` 次。例如 `send-keys -N 3 Up` 等于按三下上。

- `-X cmd`：发**复制模式命令**而不是按键。仅在面板处于 copy-mode 时有意义；自动化场景几乎用不到，知道存在即可。

- `-H`：以**十六进制**解释参数。`send-keys -H 1b 5b 41` 等价于发一个 `Up` 转义。需要发原始字节序列时才用。

### 多行输入怎么发

不要把多行命令拼成一个带 `\n` 的字符串——`\n` 不会被识别成回车。正确做法是把每行各自作为一段字面量，再单独发 `Enter`：

```bash
tmux send-keys -t "$P" 'def hello():' Enter
tmux send-keys -t "$P" '    print("hi")' Enter
tmux send-keys -t "$P" '' Enter   # 空行结束 python 函数定义
```

或者写到临时文件再让面板里的 shell 去 source/执行。

### 引号与 shell 转义

`send-keys` 的参数先经过 shell 解析再到 tmux。要发字符 `$`、反引号、`!`，按 shell 规则转义或用单引号：

```bash
tmux send-keys -t "$P" 'echo $HOME' Enter   # 单引号：$HOME 字面发，由远端 shell 展开
tmux send-keys -t "$P" "echo $HOME" Enter   # 双引号：本地先展开，远端拿到的是路径
```

---

## capture-pane：读取面板内容

### 基本形式

```
tmux capture-pane -p -t <target>
```

不加 `-p` 时，捕获结果存进 paste buffer（适合面板间复制粘贴），自动化里几乎总是要 `-p` 把内容直接打到 stdout。

### 行范围 flag

- `-S start`：起始行号。**0 是最顶部可见行**，**负数往历史里走**（`-100` = 历史里第 100 行之前），**`-` 表示最早**。
- `-E end`：结束行号。**默认是最后一可见行**，`-` 表示最末（即历史最末，目前看不到的也算）。

```bash
tmux capture-pane -p -t "$P"              # 仅当前可见区
tmux capture-pane -p -t "$P" -S -          # 从历史最早到当前底
tmux capture-pane -p -t "$P" -S - -E -     # 全部内容含历史
tmux capture-pane -p -t "$P" -S -200       # 最近 200 行 + 当前可见区
```

### 内容格式 flag

- `-J`：**Join wrapped lines + 保留尾随空格**。把 tmux 因终端宽度而折行的内容重新拼回一行，并保留行尾空格。**解析结构化输出（JSON、表格、log）时基本必加**。
- `-N`：**preserve trailing spaces**。只保留尾随空格（不拼接折行）。绝大多数情况下用 `-J` 就够了——`-J` 已经包含 `-N` 的效果。`-N` 适合"我想保留尾随空格但不要把折行拼起来"这种少见场景。
- `-e`：**包含转义序列**（颜色、加粗、下划线）。要把面板渲染成 HTML 之类的才用；纯解析建议不要。
- `-C`：**Escape non-printable characters as octal**。打印不可见字节，调试用。
- `-T`：**Trim trailing whitespace lines**。去掉尾部所有的空行。

### 推荐组合

```bash
# 解析最近输出（含已滚出区），适合等待提示符
tmux capture-pane -p -t "$P" -S -200 -J

# 完整 transcript（保存日志）
tmux capture-pane -p -t "$P" -S - -E - -J -T
```

---

## pipe-pane：把面板输出实时管道到外部命令

### 基本形式

```bash
tmux pipe-pane -t <target> 'cat >> /tmp/pane.log'
tmux pipe-pane -t <target>           # 不带命令则停止管道
```

每当面板里有新输出，tmux 把它**同步**喂到该 shell 命令的 stdin。和 `capture-pane` 互补：capture 是"现在抓快照"，pipe 是"持续录制"。

### 关键 flag

- `-o`：**toggle**。再调一次同样的命令会关掉而不是开第二份。批量绑定到键位时方便。
- `-O`：**只把出去的（output）管道**，不管输入。
- `-I`：**反向**——把 stdin 喂进面板，效果近似 `send-keys`，但不解释键名，全部当字面量。

```bash
# 把命令的 stdout 注入到面板
echo 'ls -la' | tmux pipe-pane -I -t "$P"
```

`splitw -I` 可以把 stdin 拿来作为新面板的初始内容（不是 shell，是空面板的回显内容）：

```bash
echo 'hello' | tmux split-window -I -P -F '#{pane_id}'
```

### 真实用途

- **持续日志**：`tmux pipe-pane -t "$P" 'cat >> /tmp/p.log'`，之后 Claude 任意时刻 `tail -n 100 /tmp/p.log` 拿增量，比反复 capture 全屏轻得多。
- **实时检测条件**：管道目标命令里写匹配逻辑，例如 `tmux pipe-pane -t "$P" "grep --line-buffered ERROR >> /tmp/err.log"`。
- **录制 demo**：搭配 `script(1)` 或 asciinema。

---

## 三者搭配的决策

- 要"发一行命令然后立即知道结果" → `send-keys` + 轮询 `capture-pane`
- 要"长时间观察面板有没有出现某关键词" → `pipe-pane` + 文件 grep（不要轮询 capture，量大）
- 要"把面板当无 shell 的画布写入" → `splitw ''` 创建空面板，再 `display-message -I` 或 `pipe-pane -I` 写入

---

## 一些边界

- `send-keys` 时**面板必须存在且未被 kill**。先用 `tmux list-panes -F '#{pane_id}'` 确认还在。
- `capture-pane` 默认范围是当前面板的"可见高度"——如果终端高度变了会影响。生产用法里要么指定 `-S/-E`，要么先 `tmux refresh-client -S` 强制确认尺寸。
- `pipe-pane` 进程一旦死掉，tmux 不会自动重启——要做长期日志，命令本身写成 `while true; do ... done` 或者用 `tee -a` 追加文件。
