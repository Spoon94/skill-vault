# hao 哨兵：容忍"两段之间插连字符"的令牌损坏

> 分工：quill 设计并验收，verse 实施。分支 `fix/hao-sentinel-separator`（基于 main 8303415，PR #12 已合并）。用户已同意改匹配器。

## 背景（2026-11-27 真机实测）

pi 在一个 text-only 任务里把完成信号打印成：

```
HAO_DONE hao-6d913218-c808bdde
```

令牌两段（各 8 位十六进制）之间多了一个连字符。`SENTINEL_RE` 只认连续的十六进制，这一行不算哨兵，等待方拿不到完成证据，等到超时（`timeout after 60s; agent_status=done`）。同一场景重跑 3/3 通过，属模型偶发；约八十多次文本通道完成里出现 1 次。

后果在 text-only 模式最大：prompt 里没有 `hao done` 命令，哨兵是唯一的完成通道，默认超时 30 分钟。

协议文档早已把"重复段 / 丢前缀 / 插分隔符"列为实测出现的三种拼错形态，匹配器只容忍了前两种。

## 设计原则

**身份校验一点不放宽。** 令牌是十六进制，里面不可能有连字符，所以"两段之间恰有一个连字符"可以无歧义地去掉；去掉之后走**现有的** `SENTINEL_RE` 和 `_token_matches`，两段拼接后必须与已知令牌完全一致才接受。证据强度与完整令牌相同，不引入误判。

只容忍这一个形状（连字符，两侧各 8 位）。空格、下划线、各种长横线、`..`、多段——一律不动，保持"宁漏判不误判"。

## 改动（`hao/scripts/waiting.py`）

**不改**：`SENTINEL_RE`、`_token_matches`、`_join_wrapped_sentinels`、`_confirm_sentinel`、`_PREFIX_LINE_RE`、`_HEX_CONT_RE`。

**新增**（紧跟 `SENTINEL_RE` 之后）：

```python
# Fast-path pattern handed to `pane wait-output` (Rust regex on the herdr
# side: no lookaround, no backreferences). A superset of SENTINEL_RE that
# also matches the token's two 8-hex halves joined by a hyphen; the client
# removes that hyphen and matches with SENTINEL_RE again.
SENTINEL_RE_WIDE = re.compile(
    rf"^\s*(?:[{_PREFIX_CHARS}]|\d+\.|\|)*\s*HAO_DONE:?\s+"
    rf"((?:hao-)?[0-9a-f]{{8}}-[0-9a-f]{{8}}|(?:hao-)?[0-9a-f]{{12,32}})"
    rf"[{_TAIL_CHARS}]*$")

# A peer once printed the two halves joined by a hyphen
# ("HAO_DONE hao-6d913218-c808bdde"). Hex never contains a hyphen, so
# removing it is unambiguous and the existing identity checks then apply
# unchanged: both halves must equal the known token's. Any other separator
# (space, underscore, dash variants, several parts) is left alone.
_SPLIT_TOKEN_RE = re.compile(
    rf"^(\s*(?:[{_PREFIX_CHARS}]|\d+\.|\|)*\s*HAO_DONE:?\s+(?:hao-)?[0-9a-f]{{8}})"
    rf"-([0-9a-f]{{8}})([{_TAIL_CHARS}]*)$")


def _rejoin_split_token(line):
    """Drop a hyphen joining the token's two 8-hex halves; other lines unchanged."""
    return _SPLIT_TOKEN_RE.sub(r"\1\2\3", line, count=1)
```

**四处匹配点各加一步归一化**（先 `_rejoin_split_token`，再用原来的 `SENTINEL_RE`）：

1. `_sentinel_check`：`pane wait-output --regex` 改用 `SENTINEL_RE_WIDE.pattern`；拿到 `matched_line` 后先归一化再 `SENTINEL_RE.search`。返回值仍是**原始行**（对方实际打印的内容，作为证据）。
2. `_sentinel_scan_tail`：循环里 `SENTINEL_RE.match(_rejoin_split_token(line))`；`last` 仍记原始行。
3. `_tail_from_pane_text`：两处循环（合并折行后的那处，和按原始行回退的那处）都先归一化。这样提取答复时哨兵那一行不会混进 `tail`。
4. 以上覆盖了全部匹配点（lifecycle 模式也走 `_sentinel_check` 与 `_sentinel_scan_tail`）。

行为说明：
- 另一个任务的"连字符哨兵"在快路径命中 → 归一化后 `_token_matches` 不通过 → `stale=True`，走现有的同轮重扫（W2）。
- 台账降级、拿不到完整令牌时：16 位的哨兵（含归一化后的）照旧不匹配（现有规则："完整 token 不可得时，13-hex 以上一律不匹配"）。

## 设计已做的验证（quill）

- 按下面的代码在进程内做了原型：连字符形式（带各种前后缀装饰）被接受；空格、下划线、`–`、`—`、`..`、`--`、三段、两半 7 位或 9 位全部不接受；身份校验（第二半错、第一半错、属于别的任务）照旧；宽模式与 `SENTINEL_RE` 在 14 个样例上判定一致，唯一多接受的是连字符形式；宽模式里没有环视和反向引用；台账降级时 16 位哨兵（含归一化后的）照旧不匹配。
- 在真 herdr 上验证了服务端：`pane wait-output --regex <宽模式>` 能匹配 `HAO_DONE hao-5e1f0a2b-3c4d9a7b`（旧模式会跳过它），也照常匹配正常形式。

## 测试（新模块 `tests/hao/test_sentinel_separator.py`，装离线守卫，全部用桩）

令牌统一用运行时拼接：`SID = "5e1f0a2b3c4d"`，`TOKEN = "hao-" + SID + "9a7b"`（两半 `5e1f0a2b` / `3c4d9a7b`）。

1. **`_rejoin_split_token` 只动这一个形状**：`hao-A-B`、不带前缀的 `A-B`、带装饰的（`⏺ `、`│ `、`❯ ` 开头，`│`、` ┃`、`…` 结尾）→ 都变成连续形式。以下保持原样：空格、下划线、`–`、`—`、`..`、`--`、`A-B-C`、两半是 7 位或 9 位、连字符后面不是 8 位。
2. **身份校验不变**（`_sentinel_scan_tail`，桩 `pane read` 返回屏幕文本）：
   - 屏幕上是本任务的两半加连字符 → 返回该原始行；
   - 第二半差一位 → `None`；
   - 两半属于另一个任务 → `None`；
   - 空格分隔的同两半 → `None`。
3. **快路径**（`_sentinel_check`，桩 `pane wait-output` 的 `matched_line`）：本任务的连字符哨兵 → `(原始行, None, False)`；另一个任务的 → `(None, None, True)`（stale）；并且断言传给 wait-output 的是 `SENTINEL_RE_WIDE.pattern`。
4. **端到端**（`cmd_wait`，桩 herdr：`agent get` → done，`pane wait-output` → 本任务的连字符哨兵，`pane read` → `"answer\nHAO_DONE hao-A-B"`）：返回 `status == "done"`，`matched_line` 是**原始的**连字符行，`tail == "answer"`（哨兵行没混进答复）。
5. **台账降级**：只有 shortid、没有完整令牌时，连字符形式的 16 位哨兵不被接受。
6. **宽模式是严格超集**：对一组样例行（旧模式接受的全部形状：带/不带 `hao-`、12–32 位、各种前后缀装饰；以及不该匹配的：行中出现的 `…打印：HAO_DONE …`、只有令牌没有 `HAO_DONE`、空格/下划线分隔），断言 `SENTINEL_RE_WIDE` 与 `SENTINEL_RE` 判定一致；唯一多接受的是连字符形状。另断言 `SENTINEL_RE_WIDE.pattern` 里没有环视和反向引用（`(?=`、`(?<=`、`(?!=`、`\1`），因为 herdr 侧是 Rust regex。

验收：正常环境与 herdr 不可达两种模式全过；集成冒烟通过；**变异自检**：在未修的代码上跑这个新模块，第 2–4 项必须失败。

## 真机验证（quill 做）

在真机套件里加一个**不依赖模型**的确定性场景 `sentinel_split_by_hyphen_is_accepted`（`tests/hao/live/run_live.py`）：

- 套件的 `Ctx` 加一个只建标签页、不起 agent 的辅助（把 `new_instance` 拆出一个 `kind=None` 的分支），得到一个 shell pane。
- 在套件自己的 `HAO_STATE_DIR` 里种一条 running 记录（进程内加载 `hao/scripts/ledger.py`，`Ledger().write_running(sid, token=…, target=<pane>, prompt="probe")`）。
- 后台起 `hao wait <pane> --token <token> --no-agent --timeout 15 --json`；2 秒后 `herdr pane run <pane> "printf 'answer\nHAO_DONE hao-5e1f0a2b-3c4d9a7b\n'"`。
- 断言：等待在 printf 之后 **8 秒内**返回（说明是快路径 `pane wait-output --regex SENTINEL_RE_WIDE` 认出来的，不是 30 秒后的大窗口重扫），rc 0，`status == "done"`，`matched_line` 含 `hao-5e1f0a2b-3c4d9a7b`（原始行），`tail == "answer"`。
- 反例：另种一条记录，打印 `HAO_DONE hao-5e1f0a2b-3c4dffff`（第二半不对）→ `--timeout 8` 的等待返回 rc 4。

这个场景同时验证了 herdr 服务端接受 `SENTINEL_RE_WIDE.pattern`（Rust regex），这是桩测试验不到的。

通过后跑一遍完整真机套件（要求 44 PASS / 0 FAIL / 1 SKIP，新场景计入），再提 PR，**不合并**。

## 文档

`hao/references/protocol.md` 的「匹配器」一条补上：两段之间插连字符的形态，仅在连字符两侧各 8 位、且拼接后与已知令牌完全一致时接受（快路径用 `SENTINEL_RE_WIDE`，匹配前去掉该连字符）；其它分隔符不容忍。「peer 完成上报」里"实测出现过重复段/丢前缀/插分隔符三种拼错形态"后面注明三种都已容忍。

## 约束

- 除上面列出的新增与四处归一化外，不改等待内核和匹配器的任何逻辑；不改简报措辞。
- 自包含，入口仍是 `python3 scripts/hao`，零外部依赖。
- 测试不启动真实 agent、不发送按键（真机场景由 quill 跑）；禁止 `pkill -f` / `killall`；hao 只留在 skill 目录内。
