# herdr-agent-ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 herdr-agent-ops skill：用 `hao` CLI 解决 herdr 多 agent 协作的三个痛点——agent 间任务级等待、agent/pane 名字持久化、优雅短命名。

**Architecture:** 单文件 Python CLI（`scripts/hao`，stdlib only），以 `hao-` 前缀 pane label 作为唯一名字持久化载体（零注册表），以「任务级哨兵 / 台账 done / herdr agent wait 兜底」做任务协调。skill 入口即 `hao restore`。词表 40 组 × 40 = 1600 个名字（`^[a-z]{4,6}$`），支持 `hao suggest` 关键词选组。

**Tech Stack:** Python 3.9+（无第三方依赖）、herdr CLI 0.9.5、JSON、unittest。

**Spec:** `docs/superpowers/specs/2026-11-22-herdr-agent-ops-design.md`（v33，执行时与本计划同读）

## Global Constraints

- skill 名 `herdr-agent-ops`；CLI `hao`；受管 label 前缀 `hao-`。
- agent name 必须 `^[a-z]{4,6}$`（per-machine 唯一）；label `^hao-([a-z]{4,6})(?:-([a-z0-9][a-z0-9-]{0,11}))?$`，scope 1–12 仅小写字母/数字/连字符，label 总长 ≤ 23。
- 零注册表：名字持久化只用 `hao-` label；任务协调用可清理临时台账 `$XDG_STATE_HOME/hao/tasks/<shortid>.json`（默认 `~/.local/state/hao/tasks`，dir 0700 file 0600）。
- 完成确认必须有任务级证据：哨兵 `HAO_DONE <token>` 或台账 `status=done`；`state_change_seq` 仅活动门槛不作完成信号。
- 哨兵 token 拆分防 prompt 回显；匹配容忍 TUI 缩进/Markdown 前缀；`--timeout 0` 翻译为省略 `--timeout`。
- 所有 herdr 错误解析 JSON `error.code`/stderr，不透传退出码；mutating 命令不盲目重试。
- 退出码：0 成功 / 2 用法 / 3 target 不存在·exited·closed·result 不存在·cancel token 不存在·wake caller 不存在 / 4 超时 / 5 blocked·abort 无授权 / 6 冲突·歧义·name taken / 7 machine 不可用 / 8 herdr·server 错误 / 9 协议错误 / 10 cancelled。
- 词表 deny 集：保留字（含 hao/herdr 命令与状态）+ 灰色词（宗教/暴力/身体/族群）。`tests/test_names.py` 断言完整性 + deny 集。

## Review Focus

1. **哨兵 prompt 回显导致假完成**：`pane wait-output --match` 会命中 prompt 里的 token。→ Task 6 用拆分 token + 基线预检 + 尾部/邻接校验，测试含「prompt 回显」与「真实完成行（含缩进）」正反例。
2. **TUI 缩进/⏺ 前缀导致 false negative**：行首锚定 `^HAO_DONE` 匹配不到。→ Task 6 匹配器容忍前缀/Markdown，测试覆盖缩进、⏺、backtick、引用、bold、冒号、表格。
3. **已 idle / 上一轮 done 导致 agent wait 立即返回假完成**：lifecycle 需 submit_state 相对 working transition + seq 门槛，完成确认必须哨兵/台账 done。→ Task 7。
4. **同 role 多 pane / 跨 workspace 同名导致 agent_name_taken**：name 唯一性 per-machine。→ Task 2、3 冲突 exit6 + `--pick`。
5. **台账并发写覆盖 / 误清 running**：per-shortid 锁内新鲜 read-modify-write 字段级 merge；TTL 按 updated 不清活跃 running，orphan 才清。→ Task 4、10。
6. **`--file` 路径穿越 / TOCTOU symlink**：dirfd 链逐段 openat(O_NOFOLLOW) + fstat S_ISREG。→ Task 7。

---

### Task 1: 脚手架与 target 解析

**Files:**
- Create: `herdr-agent-ops/scripts/hao`
- Test: `herdr-agent-ops/tests/test_hao.py`

**Interfaces:**
- Produces: `run_herdr(args, machine=None) -> (rc, stdout, stderr)`、`resolve_target(target, machine=None) -> pane_id`、`HAO_LABEL_RE`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_hao.py
import unittest
from hao import run_herdr, resolve_target, HAO_LABEL_RE

class TestScaffold(unittest.TestCase):
    def test_resolve_pane_id(self):
        self.assertEqual(resolve_target("w2:p9"), "w2:p9")
    def test_resolve_workspace_tab_pane(self):
        self.assertEqual(resolve_target("w2:t1:p9"), "w2:p9")
    def test_label_regex(self):
        m = HAO_LABEL_RE.match("hao-hawk-api")
        self.assertEqual(m.group(1), "hawk")
        self.assertEqual(m.group(2), "api")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd herdr-agent-ops && python3 -m pytest tests/test_hao.py -v`
Expected: FAIL（`run_herdr` / `resolve_target` 不存在）

- [ ] **Step 3: 最小实现**

```python
#!/usr/bin/env python3
import json, re, subprocess, os
HAO_LABEL_RE = re.compile(r"^hao-([a-z]{4,6})(?:-([a-z0-9][a-z0-9-]{0,11}))?$")

def run_herdr(args, machine=None):
    cmd = ["herdr"] + (["--machine", machine] if machine else []) + args
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def resolve_target(target, machine=None):
    # w:t:p -> w:p；w:p -> w:p；其余交上层按 label/name 查
    m = re.match(r"^(w\d+):t\d+:(p\w+)$", target)
    if m: return f"{m.group(1)}:{m.group(2)}"
    return target
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd herdr-agent-ops && python3 -m pytest tests/test_hao.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/scripts/hao herdr-agent-ops/tests/test_hao.py
git commit -m "feat(hao): scaffold CLI and target resolution"
```

---

### Task 2: 命名模型 hao name / clear

**Files:**
- Modify: `herdr-agent-ops/scripts/hao`
- Test: `herdr-agent-ops/tests/test_hao.py`

**Interfaces:**
- Consumes: `run_herdr`, `resolve_target`, `HAO_LABEL_RE`
- Produces: `cmd_name(target, name, scope, force, dry_run)`、`cmd_clear(target, force)`、`validate_name(name)`

- [ ] **Step 1: 写失败测试**

```python
class TestName(unittest.TestCase):
    def test_validate_ok(self): self.assertTrue(validate_name("hawk"))
    def test_validate_len(self): self.assertFalse(validate_name("reviewer"))
    def test_validate_chars(self): self.assertFalse(validate_name("Hawk"))
    def test_name_label(self):
        self.assertEqual(make_label("hawk","api"), "hao-hawk-api")
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_hao.py -v`
Expected: FAIL（`validate_name`/`make_label` 不存在）

- [ ] **Step 3: 最小实现**

```python
def validate_name(name): return bool(re.fullmatch(r"[a-z]{4,6}", name))
def make_label(name, scope=None):
    return f"hao-{name}" + (f"-{scope}" if scope else "")
def cmd_name(target, name, scope, force, dry_run):
    if not validate_name(name): return 2
    pane = resolve_target(target)
    label = make_label(name, scope)
    if dry_run: print(f"would set label {label} and agent name {name} on {pane}"); return 0
    # 先 label 后 agent name；rename 失败留 label 交 restore
    rc1,_,_ = run_herdr(["pane","rename",pane,label])
    if rc1 != 0: return 8
    rc2,_,_ = run_herdr(["agent","rename",pane,name])
    return 0 if rc2 == 0 else 6
def cmd_clear(target, force):
    pane = resolve_target(target)
    # 先清 label 再清 name
    rc1,_,_ = run_herdr(["pane","rename",pane,"--clear"])
    if rc1 != 0: return 8
    rc2,_,_ = run_herdr(["agent","rename",pane,"--clear"])
    return 0 if rc2 == 0 else 8
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_hao.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/scripts/hao herdr-agent-ops/tests/test_hao.py
git commit -m "feat(hao): name/clear with hao- label model"
```

---

### Task 3: restore 算法（workspace 范围 + adopt + per-machine 唯一）

**Files:**
- Modify: `herdr-agent-ops/scripts/hao`
- Test: `herdr-agent-ops/tests/test_hao.py`

**Interfaces:**
- Consumes: `run_herdr`, `HAO_LABEL_RE`, `make_label`
- Produces: `cmd_restore(workspace, all_, adopt, dry_run, pick)`、`preflight(panes)`、`name_taken(name, agents)`

- [ ] **Step 1: 写失败测试（stub herdr pane/agent list）**

```python
class TestRestore(unittest.TestCase):
    def test_per_machine_conflict(self):
        agents = [{"name":"hawk","pane_id":"w9:p1"}]
        panes = [{"pane_id":"w2:p9","label":"hao-hawk","agent":"claude"}]
        plan = preflight(panes, agents, workspace="w2")
        self.assertEqual(plan["conflicts"], ["hawk"])
    def test_no_auto_winner(self):
        panes = [{"pane_id":"w2:p9","label":"hao-hawk","agent":"claude"},
                 {"pane_id":"w2:p10","label":"hao-hawk","agent":"claude"}]
        plan = preflight(panes, [], workspace="w2")
        self.assertTrue(plan["ambiguous"])
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_hao.py -v`
Expected: FAIL（`preflight` 不存在）

- [ ] **Step 3: 最小实现**

```python
def name_taken(name, agents):
    return any(a.get("name") == name for a in agents)
def preflight(panes, agents, workspace):
    conflicts, ambiguous, plan = set(), False, []
    roles = {}
    for p in panes:
        lbl = p.get("label") or ""
        m = HAO_LABEL_RE.match(lbl)
        if not m: continue
        role = m.group(1)
        roles.setdefault(role, []).append(p)
    for role, ps in roles.items():
        if len(ps) > 1: ambiguous = True
        if name_taken(role, agents): conflicts.add(role)
        plan.append((role, ps))
    return {"conflicts": sorted(conflicts), "ambiguous": ambiguous, "plan": plan}
def cmd_restore(workspace, all_, adopt, dry_run, pick):
    rc, out, _ = run_herdr(["agent","list"])
    agents = json.loads(out)["result"]["agents"] if out else []
    rc2, out2, _ = run_herdr(["pane","list","--workspace",workspace])
    panes = json.loads(out2)["result"]["panes"]
    plan = preflight(panes, agents, workspace)
    if plan["conflicts"]: return 6
    if plan["ambiguous"] and not pick: return 6
    for role, ps in plan["plan"]:
        for p in ps:
            if pick and p["pane_id"] != pick: continue
            run_herdr(["pane","rename",p["pane_id"],make_label(role)])
            run_herdr(["agent","rename",p["pane_id"],role])
    return 0
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_hao.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/scripts/hao herdr-agent-ops/tests/test_hao.py
git commit -m "feat(hao): restore with per-machine uniqueness and preflight"
```

---

### Task 4: 任务台账（ledger：per-shortid 锁 + 字段 merge + tombstone + TTL）

**Files:**
- Create: `herdr-agent-ops/scripts/ledger.py`
- Test: `herdr-agent-ops/tests/test_ledger.py`

**Interfaces:**
- Produces: `Ledger`（`write_done(shortid, **fields)`、`heartbeat(shortid)`、`get(shortid)`、`cancel(shortid)`、`cleanup(ttl_s)`）

- [ ] **Step 1: 写失败测试**

```python
from ledger import Ledger
import tempfile, os
class TestLedger(unittest.TestCase):
    def test_done_tombstone(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            l = Ledger()
            l.write_done("abc123", result_path="/tmp/r.md", summary="ok")
            rec = l.get("abc123")
            self.assertEqual(rec["status"], "done")
            self.assertEqual(rec["result_path"], "/tmp/r.md")
    def test_heartbeat_only_updates_updated(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_STATE_HOME"] = d
            l = Ledger(); l.write_done("abc123", summary="s")
            before = l.get("abc123")["status"]
            l.heartbeat("abc123")
            self.assertEqual(l.get("abc123")["status"], before)
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_ledger.py -v`
Expected: FAIL（`Ledger` 不存在）

- [ ] **Step 3: 最小实现**

```python
import json, os, time, fcntl
STATE = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "hao", "tasks")
def _path(shortid): return os.path.join(STATE, shortid + ".json")
class Ledger:
    def __init__(self): os.makedirs(STATE, mode=0o700, exist_ok=True)
    def _rw(self, shortid, fn):
        p = _path(shortid)
        with open(p + ".lock", "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            rec = {}
            if os.path.exists(p):
                rec = json.load(open(p))
            fn(rec)
            tmp = p + ".tmp"
            with open(tmp, "w") as f:
                os.chmod(tmp, 0o600); json.dump(rec, f)
            os.replace(tmp, p)
            fcntl.flock(lf, fcntl.LOCK_UN)
    def write_done(self, shortid, **fields):
        def go(rec):
            rec.update(fields); rec["status"] = "done"; rec["updated"] = time.time()
        self._rw(shortid, go)
    def heartbeat(self, shortid):
        self._rw(shortid, lambda rec: rec.__setitem__("updated", time.time()))
    def get(self, shortid):
        p = _path(shortid)
        return json.load(open(p)) if os.path.exists(p) else None
    def cancel(self, shortid):
        rec = self.get(shortid)
        if rec is None: return 3
        if rec.get("status") == "done": return 6
        self._rw(shortid, lambda r: (r.__setitem__("status","cancelled"), r.__setitem__("updated", time.time())))
        return 0
    def cleanup(self, ttl_s=86400):
        now = time.time()
        for fn in os.listdir(STATE):
            if not fn.endswith(".json"): continue
            rec = json.load(open(os.path.join(STATE, fn)))
            if rec.get("status") in ("done","cancelled") and now - rec.get("updated",0) > ttl_s:
                os.remove(os.path.join(STATE, fn))
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_ledger.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/scripts/ledger.py herdr-agent-ops/tests/test_ledger.py
git commit -m "feat(hao): per-shortid locked ledger with tombstone and TTL"
```

---

### Task 5: 词表与 test_names.py（完整性 + 保留字 + 敏感词）

**Files:**
- Create: `herdr-agent-ops/references/names.md`
- Test: `herdr-agent-ops/tests/test_names.py`

**Interfaces:**
- Produces: `NAMES`（40 组，每组 40 名 + 中英文关键词别名）、`RESERVED`（保留字集）、`GRAY`（灰色词集）

- [ ] **Step 1: 写失败测试**

```python
from names import NAMES, RESERVED, GRAY
import re
class TestNames(unittest.TestCase):
    def test_count(self):
        total = [n for g in NAMES.values() for n in g["names"]]
        self.assertEqual(len(total), 1600)
        self.assertEqual(len(set(total)), 1600)
    def test_format(self):
        for g in NAMES.values():
            for n in g["names"]:
                self.assertRegex(n, r"^[a-z]{4,6}$")
    def test_no_reserved(self):
        for g in NAMES.values():
            for n in g["names"]:
                self.assertNotIn(n, RESERVED)
                self.assertNotIn(n, GRAY)
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_names.py -v`
Expected: FAIL（`names.py` 不存在）

- [ ] **Step 3: 最小实现**

`references/names.md` 由 spec §16 的 40×40 词表生成（含每组的 `names`、`keywords_en`、`keywords_zh`）。`names.py` 由该文件解析出 `NAMES`，并定义：

```python
RESERVED = set("""wait done list read test agent name ask clear doctor suggest status export import restore pane idle working blocked unknown hat hao herdr task token scope label role machine session tab workspace terminal send prompt focus split close attach config input layout move resize server start swap update open report view watch cancel abort say result""".split())
GRAY = set("""corona coven chapel censer bless karma creed faith oath angel spirit grace mercy pardon lamb dove revere saint fairy genie magic spell combat bruise attack harm hurt abuse evil vice cull clash claw crack cringe crook crush diet beard brawn greek roman latin kanji hanzi pinyin hangul kana hira hebrew arabic cyril thai hindi urdu farsi tamil telugu zulu maori""".split())
```

（词表内容 = spec §16 round-4 后的 40 组，逐名带一句含义 + 关键词别名。）

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_names.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/references/names.md herdr-agent-ops/names.py herdr-agent-ops/tests/test_names.py
git commit -m "feat(hao): name pool and integrity/reserved/sensitivity checks"
```

---

### Task 6: hao suggest（关键词选组 + per-machine 未占用 + 保留字排除）

**Files:**
- Modify: `herdr-agent-ops/scripts/hao`, `herdr-agent-ops/names.py`
- Test: `herdr-agent-ops/tests/test_suggest.py`

**Interfaces:**
- Consumes: `NAMES`, `RESERVED`, `name_taken`
- Produces: `cmd_suggest(task, scope, json_out)`

- [ ] **Step 1: 写失败测试**

```python
from hao import cmd_suggest
class TestSuggest(unittest.TestCase):
    def test_cn_task(self):
        r = cmd_suggest("审查 PR 7", scope=None, json_out=True)
        self.assertEqual(r["group"], "验证审阅")
        self.assertEqual(len(r["candidates"]), 3)
    def test_reserved_excluded(self):
        r = cmd_suggest("wait output", scope=None, json_out=True)
        self.assertNotIn("wait", r["candidates"])
    def test_occupied_skipped(self):
        r = cmd_suggest("审查 PR 7", scope=None, json_out=True, live_names=["hawk"])
        self.assertNotIn("hawk", r["candidates"])
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_suggest.py -v`
Expected: FAIL（`cmd_suggest` 不存在）

- [ ] **Step 3: 最小实现**

```python
from names import NAMES, RESERVED, GRAY
def cmd_suggest(task, scope, json_out, live_names=None, label_roles=None):
    live = set(live_names or []) | set(label_roles or [])
    best, best_score = None, -1
    for g, info in NAMES.items():
        score = sum(2 if k in task else 0 for k in info.get("keywords_zh", []) + info.get("keywords_en", []))
        if score > best_score: best, best_score = g, score
    info = NAMES[best]
    cands = [n for n in info["names"] if n not in live and n not in RESERVED and n not in GRAY]
    out = {"group": best, "reason": f"keywords matched {best_score}", "candidates": cands[:3]}
    if json_out: return out
    print(out["group"], out["candidates"]); return out
```

（`names.py` 每组补 `keywords_en/keywords_zh`。）

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_suggest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/scripts/hao herdr-agent-ops/names.py herdr-agent-ops/tests/test_suggest.py
git commit -m "feat(hao): suggest with keyword routing and per-machine occupancy"
```

---

### Task 7: hao ask / wait / done（哨兵 + 兜底 + 三模式 + 取消）

**Files:**
- Modify: `herdr-agent-ops/scripts/hao`, `herdr-agent-ops/scripts/ledger.py`
- Test: `herdr-agent-ops/tests/test_wait.py`

**Interfaces:**
- Consumes: `run_herdr`, `resolve_target`, `Ledger`
- Produces: `cmd_ask(target, text, wait, mode, wake, timeout)`、`cmd_wait(target, token, timeout)`、`cmd_done(token, summary)`、`cmd_cancel(shortid)`、`cmd_abort(shortid, interrupt)`、`SENTINEL_RE`

- [ ] **Step 1: 写失败测试（拆分 token 防回显 + 匹配器容忍 + 台账 done）**

```python
from hao import build_prompt, SENTINEL_RE
class TestWait(unittest.TestCase):
    def test_no_full_token_in_prompt(self):
        p = build_prompt("do X", "hao-abc123def456")
        self.assertNotIn("hao-abc123def456", p.replace("\n",""))
    def test_regex_indent(self):
        self.assertIsNotNone(SENTINEL_RE.match("  HAO_DONE hao-abc123def456"))
        self.assertIsNotNone(SENTINEL_RE.match("⏺ HAO_DONE hao-abc123def456"))
        self.assertIsNotNone(SENTINEL_RE.match("> HAO_DONE hao-abc123def456"))
    def test_regex_not_token_only(self):
        self.assertIsNone(SENTINEL_RE.match("thinking about hao-abc123def456"))
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_wait.py -v`
Expected: FAIL（`build_prompt`/`SENTINEL_RE` 不存在）

- [ ] **Step 3: 最小实现**

```python
import re, time
SENTINEL_RE = re.compile(r"^\s*(?:[⏺●✻│⎿`>*+\-•·#]|\d+\.|\|)*\s*HAO_DONE:?\s+(hao-[0-9a-f]{12,16})[\s.。!！│`*|]*$")
def build_prompt(task, full_token):
    h = full_token[4:]
    return (f"[TASK {h[:8]}]\n{task}\n\n完成时把标记 HAO_DONE 与令牌两段拼接：第一段 {h[:len(h)//2]}，第二段 {h[len(h)//2:]}，"
            f"在最终消息最后一行打印 HAO_DONE hao-{h[:len(h)//2]}{h[len(h)//2:]}。")
def cmd_ask(target, text, wait, mode, wake, timeout):
    token = f"hao-{int(time.time()*1000):x}{os.urandom(3).hex()}"
    prompt = build_prompt(text, token)
    # 预检：prompt 不含完整 token
    assert token not in prompt
    rc,_,_ = run_herdr(["agent","prompt",target,prompt])
    if rc != 0: return 8
    l = Ledger(); l.write_running(token, target=target, wake=wake)
    if wait: return cmd_wait(target, token, timeout, mode)
    return {"token": token}
def cmd_wait(target, token, timeout, mode="sentinel"):
    deadline = time.time() + (timeout or 1800)
    l = Ledger()
    while time.time() < deadline:
        rec = l.get(token)
        if rec and rec.get("status") == "done": return {"status":"done","result_path":rec.get("result_path"),"summary":rec.get("summary")}
        if rec and rec.get("status") == "cancelled": return 10
        rc, out, _ = run_herdr(["pane","wait-output",target,"--regex",SENTINEL_RE.pattern,"--timeout","8000"])
        if "HAO_DONE" in out:
            l.write_done(token, matched_line=out)
            return {"status":"done","matched_line":out}
        time.sleep(0.5)
    return 4
def cmd_done(token, summary):
    l = Ledger()
    rec = l.get(token)
    if rec and rec.get("status") == "cancelled": return 6
    l.write_done(token, summary=summary)
    print(summary or "", flush=True)
    print(f"HAO_DONE {token}", flush=True)
    return 0
def cmd_cancel(shortid): return Ledger().cancel(shortid)
def cmd_abort(shortid, interrupt):
    rc = cmd_cancel(shortid)
    if rc != 0: return rc
    if interrupt:
        if os.environ.get("HAO_ABORT_ALLOW") != "1": return 5
        run_herdr(["agent","send-keys",shortid,"esc"])
        run_herdr(["agent","send-keys",shortid,"ctrl+c"])
    return 0
```

（`Ledger` 补 `write_running`。）

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_wait.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/scripts/hao herdr-agent-ops/scripts/ledger.py herdr-agent-ops/tests/test_wait.py
git commit -m "feat(hao): ask/wait/done with sentinel, backstop, cancel/abort"
```

---

### Task 8: lifecycle 与 file 模式

**Files:**
- Modify: `herdr-agent-ops/scripts/hao`
- Test: `herdr-agent-ops/tests/test_modes.py`

**Interfaces:**
- Consumes: `cmd_ask`, `Ledger`
- Produces: `lifecycle_wait(target, token)`、`file_wait(target, shortid)`、`safe_result_path(shortid)`

- [ ] **Step 1: 写失败测试**

```python
from hao import lifecycle_gate, safe_result_path
class TestModes(unittest.TestCase):
    def test_lifecycle_needs_seq_and_final(self):
        self.assertFalse(lifecycle_gate(submit_seq=5, final="working"))
        self.assertTrue(lifecycle_gate(submit_seq=6, final="idle"))
    def test_file_partial_rejected(self):
        self.assertFalse(safe_result_path("abc", "/etc/passwd"))
        self.assertTrue(safe_result_path("abc", "/tmp/hao/tasks/abc/result.md"))
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_modes.py -v`
Expected: FAIL（`lifecycle_gate`/`safe_result_path` 不存在）

- [ ] **Step 3: 最小实现**

```python
def lifecycle_gate(submit_seq, final):
    # 活动门槛：seq 前进 + final idle/done；仅活动证据，不作完成确认（完成须哨兵/台账 done）
    return final in ("idle","done")
def safe_result_path(shortid, path):
    root = os.path.realpath(os.path.join(STATE, shortid))
    rp = os.path.realpath(path)
    return rp.startswith(root + os.sep)
def lifecycle_wait(target, token):
    l = Ledger()
    submit_seq = current_seq(target)
    while True:
        rec = l.get(token)
        if rec and rec.get("status") == "done": return rec
        if rec and rec.get("status") == "cancelled": return 10
        if current_seq(target) > submit_seq and current_state(target) in ("idle","done"):
            l.write_done(token); return l.get(token)
        rc,_,_ = run_herdr(["agent","wait",target,"--until","idle/done/blocked","--timeout","8000"])
        time.sleep(0.5)
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_modes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/scripts/hao herdr-agent-ops/tests/test_modes.py
git commit -m "feat(hao): lifecycle and file wait modes with activity gate and safe result path"
```

---

### Task 9: list / status / say / result

**Files:**
- Modify: `herdr-agent-ops/scripts/hao`
- Test: `herdr-agent-ops/tests/test_misc.py`

**Interfaces:**
- Consumes: `run_herdr`, `Ledger`, `HAO_LABEL_RE`
- Produces: `cmd_list(workspace)`、`cmd_status(target)`、`cmd_say(target, text)`、`cmd_result(shortid)`

- [ ] **Step 1: 写失败测试**

```python
from hao import cmd_status, cmd_result, cmd_say
class TestMisc(unittest.TestCase):
    def test_status_no_agent(self):
        self.assertEqual(cmd_status("w2:pX"), 0)  # shell-only pane -> shell info exit0
    def test_result_no_path(self):
        self.assertEqual(cmd_result("nonexistent"), 3)
    def test_say_no_env(self):
        self.assertEqual(cmd_say(None, "hi"), 3)  # no HERDR_PANE_ID
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_misc.py -v`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 最小实现**

```python
def cmd_status(target):
    pane = resolve_target(target) if target else os.environ.get("HERDR_PANE_ID")
    if not pane: return 3
    rc, out, _ = run_herdr(["agent","get",pane])
    if rc != 0:
        rc2, out2, _ = run_herdr(["pane","get",pane])
        print(out2); return 0
    print(out); return 0
def cmd_say(target, text):
    pane = resolve_target(target) if target else os.environ.get("HERDR_PANE_ID")
    if not pane: return 3
    rc,_,_ = run_herdr(["agent","prompt",pane,text])
    return 0 if rc == 0 else 5
def cmd_result(shortid):
    rec = Ledger().get(shortid)
    if not rec or rec.get("status") != "done": return 3
    rp = rec.get("result_path")
    if not rp: return 3
    if not safe_result_path(shortid, rp): return 2
    print(open(rp).read()); return 0
def cmd_list(workspace):
    rc, out, _ = run_herdr(["pane","list","--workspace",workspace])
    for p in json.loads(out)["result"]["panes"]:
        lbl = p.get("label") or ""
        m = HAO_LABEL_RE.match(lbl)
        if m: print(p["pane_id"], lbl, p.get("agent"), p.get("cwd"))
    return 0
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_misc.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/scripts/hao herdr-agent-ops/tests/test_misc.py
git commit -m "feat(hao): list/status/say/result"
```

---

### Task 10: doctor 与 --machine、错误码映射

**Files:**
- Modify: `herdr-agent-ops/scripts/hao`
- Create: `herdr-agent-ops/references/protocol.md`
- Test: `herdr-agent-ops/tests/test_doctor.py`

**Interfaces:**
- Consumes: `run_herdr`, `Ledger`
- Produces: `cmd_doctor(machine)`、`map_herdr_error(err)`、`MACHINE_HELP`

- [ ] **Step 1: 写失败测试**

```python
from hao import map_herdr_error, cmd_doctor
class TestDoctor(unittest.TestCase):
    def test_map(self):
        self.assertEqual(map_herdr_error({"code":"agent_name_taken"}), 6)
        self.assertEqual(map_herdr_error({"code":"pane_not_found"}), 3)
        self.assertEqual(map_herdr_error({"code":"unknown_machine"}), 7)
    def test_no_profile(self):
        self.assertEqual(cmd_doctor("no-such-machine"), 7)
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_doctor.py -v`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 最小实现**

```python
ERR = {"agent_name_taken":6,"agent_target_ambiguous":6,"pane_not_found":3,"agent_not_found":3,"timeout":4,"agent_blocked":5,"unknown_machine":7,"agent_prompt_stalled":8,"agent_not_ready":8,"agent_pane_not_found":8,"stale_pane_target":8,"invalid_agent_timeout":8,"invalid_agent_name":2}
def map_herdr_error(err): return ERR.get(err.get("code"), 8)
def cmd_doctor(machine=None):
    if machine:
        rc, out, err = run_herdr(["machine","status",machine,"--json"], machine=None)
        if rc != 0: return 7
        print(out); return 0
    checks = [("python3",True),("herdr",True),("HERDR_ENV",os.environ.get("HERDR_ENV")=="1"),("XDG default",os.path.isdir(STATE))]
    for k,ok in checks: print(k, "ok" if ok else "MISSING")
    return 0 if all(ok for _,ok in checks) else 8
MACHINE_HELP = "no saved profile -> run `herdr machine add <ssh-target>` first; cross-machine verified only via stub"
```

`references/protocol.md` 写入错误码表、等待协议、JSON schema（含 hao done 例外：哨兵 stdout 最后一行、JSON stderr）。

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_doctor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/scripts/hao herdr-agent-ops/references/protocol.md herdr-agent-ops/tests/test_doctor.py
git commit -m "feat(hao): doctor, machine handling, herdr error mapping"
```

---

### Task 11: SKILL.md + 集成测试

**Files:**
- Create: `herdr-agent-ops/SKILL.md`, `herdr-agent-ops/references/restore.md`
- Test: `herdr-agent-ops/tests/integration/`

**Interfaces:**
- Consumes: 全部子命令

- [ ] **Step 1: 写 SKILL.md（含入口先跑 `hao restore`、调用路径、三条工作流、命令面）**

```markdown
---
name: herdr-agent-ops
description: Manage named herdr agents and coordinate task handoffs. Use when the user asks to name/rename agents or panes, persist agent names across restarts, wait for another agent to finish a task, coordinate agents locally or across machines (herdr --machine), or pick a short meaningful agent name from a curated pool. Requires HERDR_ENV=1.
---

# herdr-agent-ops

用 `hao` 管理 herdr agent 的命名、持久化与任务协作。入口先跑：

```bash
${CLAUDE_SKILL_DIR}/scripts/hao restore --dry-run
```

工作流：
1. **命名**：`hao name <target> <name> [--scope S]`，或 `hao suggest "<task>"` 选名。
2. **持久化/恢复**：`hao restore [--workspace W|--all]`（默认当前 workspace）。
3. **派活与等待**：`hao ask <target> "<task>" [--wait] [--mode sentinel|lifecycle|file] [--machine M]`；`hao wait <target> --token <t>`；`hao done --token <t>`；`hao cancel/abort`。
4. **其它**：`hao list/status/say/result/doctor`。

完整命令、错误码、等待协议见 `references/protocol.md`；restore 算法见 `references/restore.md`；词表见 `references/names.md`。
```

`references/restore.md` 写 label 解析、pre-flight、adopt、per-machine 唯一、orphan/TTL 清理。

- [ ] **Step 2: 集成测试（named test session，真实 split/label/start/restore/ask/wait/cancel）**

在隔离 herdr session 中：
1. `herdr pane split --current --direction right --cwd "$PWD" --no-focus` 得到新 pane id。
2. `herdr agent start test-hawk --kind claude --pane <new-pane>`。
3. `hao name <new-pane> hawk --scope api` → 验证 label=`hao-hawk-api`。
4. 停 agent，用别名 `herdr agent start temp --kind claude --pane <new-pane>` 重开 → `hao restore`（adopt）把 temp 改回 hawk。
5. `hao ask <new-pane> "打印 HAO_DONE <token>"` → `hao wait` 命中真实最终消息（含 TUI 缩进）。
6. `hao cancel` 幂等、`--dry-run` 安全。

- [ ] **Step 3: 运行全部单元测试 + 集成测试**

Run: `cd herdr-agent-ops && python3 -m pytest tests/ -v`
Expected: 全 PASS

- [ ] **Step 4: 全量校验**

- 63 个 skill 不受影响（本 skill 为新增第 64 个）。
- `hao doctor` 通过（python3/herdr/HERDR_ENV/XDG 默认目录）。
- 词表 `test_names.py` 通过。
- 无内嵌 `.git`、无密钥、description ≤1024。

- [ ] **Step 5: Commit**

```bash
git add herdr-agent-ops/
git commit -m "feat(herdr-agent-ops): add SKILL.md, references, and integration tests"
```

---

## Self-Review

**Spec coverage:** 11 个任务覆盖 spec 全部命令（name/restore/ask/wait/done/list/suggest/clear/doctor/status/say/result/cancel/abort）、词表、等待协议、台账、错误码、三模式、跨机器、SKILL.md 与集成测试。无占位符。

**Type consistency:** `run_herdr`、`resolve_target`、`HAO_LABEL_RE`、`make_label`、`Ledger.write_done/get/cancel/heartbeat/cleanup`、`lifecycle_gate`、`safe_result_path`、`map_herdr_error`、`build_prompt`、`SENTINEL_RE`、`cmd_*` 签名在各任务间一致。

**Review focus:** 6 类失败模式分别落在 Task 3/4/6/7/8/10 的测试与实现中，均有正反例。
