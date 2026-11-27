#!/usr/bin/env python3
"""Optional real-machine scenario suite for the hao skill.

Not part of the unit-test discovery: this file is not named test_*.py and
this directory has no __init__.py. It creates one throwaway agent instance
in a background herdr tab and removes it (plus the ledger) in `finally`.

    python3 tests/hao/live/run_live.py --list
    HERDR_ENV=1 HERDR_WORKSPACE_ID=w2 python3 tests/hao/live/run_live.py --quick
"""
import argparse
import importlib.machinery
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SKILL_ROOT = os.path.join(REPO_ROOT, "hao")
HAO = os.path.join(SKILL_ROOT, "scripts", "hao")
DEFAULT_KINDS = "pi"


class Skip(Exception):
    pass


class Scenario:
    def __init__(self, name, fn, group, slow, isolate=False):
        self.name, self.fn, self.group = name, fn, group
        self.slow, self.isolate = slow, isolate


SCENARIOS = []


def scenario(name, group="", slow=False, isolate=False):
    """isolate=True: the scenario runs against its own throwaway instance.

    Scenarios that leave unfinished work behind (cancelled or interrupted
    long tasks) must not run on the shared peer: pi keeps the queued prompts
    and resumes them after an interrupt, so later scenarios would inherit a
    busy, confused peer."""
    def deco(fn):
        SCENARIOS.append(Scenario(name, fn, group, slow, isolate))
        return fn
    return deco


def last_json(text):
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except Exception:
        return None


class Ctx:
    def __init__(self, workspace, state, kinds, quick):
        self.workspace = workspace
        self.state = state
        self.kinds = kinds
        self.quick = quick
        self.pane = None
        self.tab = None
        self.extra_tabs = []
        self.checks = []
        self.env = dict(os.environ)
        self.env["HAO_STATE_DIR"] = state
        self.env.setdefault("HERDR_ENV", "1")
        self.last_file_result = None
        self.agent_seq = 0

    def agent_name(self):
        """A herdr agent name unique within the run.

        The pid makes it unique across runs too: an instance left behind by
        a crashed run is then reported as `agent_name_taken` instead of
        being silently collided with. (A fixed name made a second instance
        fail whenever the shared peer had not been renamed yet.)"""
        self.agent_seq += 1
        base = "ls" + str(os.getpid())[-5:]
        return base if self.agent_seq == 1 else "%sx%d" % (base, self.agent_seq)

    # ---------------------------------------------------------- plumbing
    def hao(self, args, timeout=None, env=None):
        args = list(args)
        if timeout is None:
            timeout = 120
            if "--timeout" in args:
                try:
                    timeout = int(args[args.index("--timeout") + 1]) + 45
                except (ValueError, IndexError):
                    pass
        return subprocess.run([sys.executable, HAO] + args,
                              capture_output=True, text=True, timeout=timeout,
                              env=env or self.env)

    def hao_json(self, args, timeout=None, env=None):
        p = self.hao(args, timeout=timeout, env=env)
        return p.returncode, last_json(p.stdout), p.stdout, p.stderr

    def herdr(self, args, timeout=30):
        return subprocess.run(["herdr"] + list(args), capture_output=True,
                              text=True, timeout=timeout, env=self.env)

    def herdr_json(self, args, timeout=30):
        p = self.herdr(args, timeout=timeout)
        return p.returncode, last_json(p.stdout), p.stdout, p.stderr

    def check(self, desc, ok, detail=""):
        self.checks.append((bool(ok), desc, detail))
        return bool(ok)

    # ---------------------------------------------------------- lifecycle
    def agent_status(self, pane=None):
        rc, data, _, _ = self.herdr_json(["agent", "get", pane or self.pane])
        if rc != 0 or not isinstance(data, dict):
            return None
        return (data.get("result") or {}).get("agent", {}).get(
            "agent_status")

    def settle(self, timeout=40):
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self.agent_status()
            if st in ("idle", "done"):
                return True
            time.sleep(0.5)
        return False

    def reset(self, name="moth", role="reviewer"):
        self.settle()
        args = ["name", self.pane, name]
        if role is not None:
            args += ["--role", role]
        args.append("--json")
        return self.hao_json(args)

    def ask(self, text, name="fern", role="developer", extra=(),
            timeout=120, wait=True):
        self.reset(name, role)
        args = ["ask", self.pane, text]
        if wait:
            args += ["--wait"]
        args += ["--timeout", str(timeout), "--json"]
        args += list(extra)
        return self.hao_json(args)

    def answer(self, data, needle):
        if not isinstance(data, dict):
            return False
        text = " ".join(str(data.get(k) or "")
                        for k in ("summary", "tail", "last_line"))
        return needle in text

    def pane_read(self, lines=300, pane=None):
        p = self.herdr(["pane", "read", pane or self.pane,
                        "--source", "recent-unwrapped",
                        "--lines", str(lines)])
        return p.stdout

    def _ledger_mod(self):
        path = os.path.join(SKILL_ROOT, "scripts", "ledger.py")
        loader = importlib.machinery.SourceFileLoader("hao_live_ledger", path)
        mod = types.ModuleType("hao_live_ledger")
        loader.exec_module(mod)
        return mod

    def _with_state(self, fn):
        saved = os.environ.get("HAO_STATE_DIR")
        os.environ["HAO_STATE_DIR"] = self.state
        try:
            return fn()
        finally:
            if saved is None:
                os.environ.pop("HAO_STATE_DIR", None)
            else:
                os.environ["HAO_STATE_DIR"] = saved

    def seed_running(self, sid, token, pane, prompt="probe"):
        mod = self._ledger_mod()
        self._with_state(lambda: mod.Ledger().write_running(
            sid, token=token, target=pane, prompt=prompt))

    def consume_record(self, sid):
        mod = self._ledger_mod()
        self._with_state(lambda: mod.Ledger().consume(sid))

    def pane_flat(self, lines=400, pane=None):
        """Pane text with whitespace and border glyphs removed.

        pi hard-wraps a pasted prompt at about 48 columns and draws a right
        border, so a phrase can be split across display lines with a border
        glyph in between ("…正文不超过 15 │" / "行；…"); match on this form."""
        return re.sub(r"[\s│┃|]+", "", self.pane_read(lines, pane))

    def input_box_text(self):
        """Text between the two separator lines of pi's input box.

        Returns None when no box is found on the visible pane (so a caller
        cannot pass vacuously)."""
        p = self.herdr(["pane", "read", self.pane, "--source", "visible",
                        "--lines", "12"])
        lines = [l.rstrip() for l in p.stdout.splitlines()]
        seps = [i for i, l in enumerate(lines)
                if len(l.strip()) >= 10 and set(l.strip()) <= set("─━-")]
        if len(seps) < 2:
            return None
        return " ".join(l.strip() for l in lines[seps[-2] + 1:seps[-1]]
                        if l.strip())

    def new_instance(self, kind="pi", label="hao-live-extra",
                     wait=6):
        p = self.herdr(["tab", "create", "--workspace", self.workspace,
                        "--cwd", "/tmp", "--label", label, "--no-focus"])
        if p.returncode != 0:
            raise Skip("tab create failed: " + p.stderr.strip()[:200])
        data = last_json(p.stdout) or {}
        res = data.get("result") or {}
        tab = res.get("tab_id") or (res.get("tab") or {}).get("tab_id")
        if not tab:
            raise Skip("tab create returned no tab_id")
        pane = None
        for _ in range(20):
            q = self.herdr_json(["pane", "list",
                                 "--workspace", self.workspace])
            for row in ((q[1] or {}).get("result") or {}).get("panes", []):
                if row.get("tab_id") == tab:
                    pane = row.get("pane_id")
                    break
            if pane:
                break
            time.sleep(0.25)
        if not pane:
            self.herdr(["tab", "close", tab])
            raise Skip("no pane found in new tab")
        if kind is None:
            self.extra_tabs.append(tab)
            return tab, pane
        cmd = ["agent", "start", self.agent_name(), "--kind", kind,
               "--pane", pane, "--timeout", "60000"]
        if kind == "claude":
            cmd += ["--", "--dangerously-skip-permissions"]
        a = self.herdr(cmd, timeout=75)
        if a.returncode != 0:
            self.herdr(["tab", "close", tab])
            raise Skip(f"agent start {kind} failed: "
                       + (a.stderr or a.stdout).strip()[:200])
        time.sleep(45 if kind == "claude" else wait)
        self.extra_tabs.append(tab)
        return tab, pane

    def close_tab(self, tab):
        if tab:
            self.herdr(["tab", "close", tab], timeout=20)
            if tab in self.extra_tabs:
                self.extra_tabs.remove(tab)

    def state_files(self):
        try:
            return [f for f in os.listdir(self.state)]
        except OSError:
            return []

    def task_running(self, data):
        tasks = (data or {}).get("tasks") or {}
        return len(tasks.get("running") or [])


# ---------------------------------------------------------------- naming
@scenario("name_sets_label_with_role", "naming")
def name_sets_label_with_role(ctx):
    rc, d, _, err = ctx.reset("moth", "arbiter")
    ctx.check("name rc 0", rc == 0, err)
    ctx.check("role arbiter", (d or {}).get("role") == "arbiter", d)
    ctx.check("tier top", (d or {}).get("tier") == "top", d)
    q = ctx.herdr_json(["pane", "get", ctx.pane])[1] or {}
    label = ((q.get("result") or {}).get("pane") or {}).get("label")
    ctx.check("herdr label", label == "hao-moth-arbiter", label)


@scenario("name_keeps_role_when_omitted", "naming")
def name_keeps_role_when_omitted(ctx):
    ctx.reset("lens", "reviewer")
    rc, d, _, err = ctx.hao_json(["name", ctx.pane, "lens", "--json"])
    ctx.check("name rc 0", rc == 0, err)
    ctx.check("kept true", (d or {}).get("kept") is True, d)
    ctx.check("label keeps role",
              (d or {}).get("label") == "hao-lens-reviewer", d)


@scenario("name_empty_role_clears", "naming")
def name_empty_role_clears(ctx):
    ctx.reset("dove", "reviewer")
    rc, d, _, err = ctx.hao_json(["name", ctx.pane, "dove",
                                  "--role", "", "--json"])
    ctx.check("name rc 0", rc == 0, err)
    ctx.check("role null", (d or {}).get("role") is None, d)
    ctx.check("tier null", (d or {}).get("tier") is None, d)
    ctx.check("kept false", (d or {}).get("kept") is False, d)
    rc2, s, _, _ = ctx.hao_json(["status", ctx.pane, "--json"])
    ctx.check("status role null",
              rc2 == 0 and (s or {}).get("role") is None, s)


@scenario("name_unknown_role_exits_2", "naming")
def name_unknown_role_exits_2(ctx):
    rc, d, _, err = ctx.hao_json(["name", ctx.pane, "moth",
                                  "--role", "foo", "--json"])
    ctx.check("rc 2", rc == 2, rc)
    ctx.check("lists roles", "reviewer" in (err + json.dumps(d or {})),
              err)
    ctx.check("lists arbiter", "arbiter" in (err + json.dumps(d or {})),
              err)
    ctx.check("no traceback", "Traceback" not in err, err)


@scenario("status_shows_role_tier_group", "naming")
def status_shows_role_tier_group(ctx):
    ctx.reset("hawk", "reviewer")
    rc, d, _, err = ctx.hao_json(["status", ctx.pane, "--json"])
    ctx.check("status rc 0", rc == 0, err)
    ctx.check("role reviewer", (d or {}).get("role") == "reviewer", d)
    ctx.check("tier mid", (d or {}).get("tier") == "mid", d)
    ctx.check("group 设计评审", (d or {}).get("group") == "设计评审", d)
    p = ctx.hao(["status", ctx.pane, "--text"])
    ctx.check("text has role", "role: reviewer" in p.stdout, p.stdout)


@scenario("list_shows_role_and_tier", "naming")
def list_shows_role_and_tier(ctx):
    ctx.reset("fern", "developer")
    rc, d, _, _ = ctx.hao_json(["list", "--json"])
    row = next((r for r in ((d or {}).get("panes") or [])
                if r.get("pane_id") == ctx.pane), None)
    ctx.check("list rc 0", rc == 0, rc)
    ctx.check("row role", bool(row) and row.get("role") == "developer", row)
    ctx.check("row tier", bool(row) and row.get("tier") == "low", row)
    p = ctx.hao(["list"])
    ctx.check("text has role/tier",
              "developer" in p.stdout and "low" in p.stdout, p.stdout)


@scenario("suggest_live_labels", "naming")
def suggest_live_labels(ctx):
    rc, d, _, _ = ctx.hao_json(
        ["suggest", "review the PR", "--live-labels", "hao-hawk-dev",
         "--live-names", "--json"])
    ctx.check("suggest rc 0", rc == 0, rc)
    ctx.check("candidates", isinstance((d or {}).get("candidates"), list), d)
    p = ctx.hao(["suggest", "review", "--label-roles", "x"])
    ctx.check("old flag rejected", p.returncode == 2, p.returncode)


@scenario("legacy_label_parses_with_null_tier", "naming")
def legacy_label_parses_with_null_tier(ctx):
    ctx.settle()
    ctx.herdr(["pane", "rename", ctx.pane, "hao-moth-ops"])
    rc, d, _, err = ctx.hao_json(["status", ctx.pane, "--json"])
    ctx.check("status rc 0", rc == 0, err)
    ctx.check("role ops", (d or {}).get("role") == "ops", d)
    ctx.check("tier null", (d or {}).get("tier") is None, d)
    ctx.reset("moss", "developer")


# ---------------------------------------------------------------- tiers
@scenario("ask_top_tier", "briefs", slow=False)
def ask_top_tier(ctx):
    rc, d, _, err = ctx.ask("42 加 8 等于多少？只回答数字。",
                            name="moth", role="arbiter", timeout=120)
    ctx.check("ask rc 0", rc == 0, err)
    ctx.check("done", (d or {}).get("status") == "done", d)
    ctx.check("tier top", (d or {}).get("tier") == "top", d)
    ctx.check("cap 15", (d or {}).get("max_lines") == 15, d)
    ctx.check("answer 50", ctx.answer(d, "50"), d)


@scenario("ask_low_tier", "briefs")
def ask_low_tier(ctx):
    rc, d, _, err = ctx.ask("只回答 low-ok。", name="fern",
                            role="developer", timeout=120)
    ctx.check("ask rc 0", rc == 0, err)
    ctx.check("tier low", (d or {}).get("tier") == "low", d)
    ctx.check("cap null", (d or {}).get("max_lines") is None, d)


@scenario("ask_mid_tier_max_lines_override", "briefs")
def ask_mid_tier_max_lines_override(ctx):
    rc, d, _, err = ctx.ask("只回答 mid-ok。", name="hawk",
                            role="reviewer", timeout=120,
                            extra=["--max-lines", "3"])
    ctx.check("ask rc 0", rc == 0, err)
    ctx.check("tier mid", (d or {}).get("tier") == "mid", d)
    ctx.check("cap 3", (d or {}).get("max_lines") == 3, d)


@scenario("ask_unroled_target", "briefs")
def ask_unroled_target(ctx):
    ctx.reset("dove", "")
    rc, d, _, err = ctx.hao_json(
        ["ask", ctx.pane, "只回答 unroled-ok。", "--wait",
         "--timeout", "120", "--json"])
    ctx.check("ask rc 0", rc == 0, err)
    ctx.check("tier null", (d or {}).get("tier") is None, d)
    ctx.check("cap null", (d or {}).get("max_lines") is None, d)


@scenario("ask_rejects_negative_max_lines", "briefs")
def ask_rejects_negative_max_lines(ctx):
    ctx.settle()
    rc, d, _, err = ctx.hao_json(
        ["ask", ctx.pane, "x", "--max-lines", "-1", "--json"])
    ctx.check("rc 2", rc == 2, rc)
    ctx.check("mentions max-lines", "max-lines" in err.lower(), err)
    _, s, _, _ = ctx.hao_json(["status", ctx.pane, "--json"])
    ctx.check("no dispatch", ctx.task_running(s) == 0, s)


@scenario("compact_brief_is_shorter", "briefs")
def compact_brief_is_shorter(ctx):
    loader = importlib.machinery.SourceFileLoader("hao_live_mod", HAO)
    mod = types.ModuleType("hao_live_mod")
    loader.exec_module(mod)
    tok = "hao-" + "ab" * 8
    top = mod.build_prompt("x", tok, tier="top")
    low = mod.build_prompt("x", tok, tier="low")
    ctx.check("top shorter", len(top) < len(low), (len(top), len(low)))
    # What was actually sent is recorded in the task's ledger record. The
    # peer's pane is not a reliable witness: pi sometimes clears the screen.
    ctx.reset("moth", "arbiter")
    rc, d, _, err = ctx.hao_json(
        ["ask", ctx.pane, "只回答 compact-ok。", "--json", "--timeout", "120"])
    sid = (d or {}).get("shortid")
    ctx.check("async ask", rc == 0 and bool(sid), err)
    prompt = ""
    if sid:
        try:
            with open(os.path.join(ctx.state, sid + ".json")) as f:
                prompt = (json.load(f) or {}).get("prompt") or ""
        except (OSError, ValueError):
            pass
    ctx.check("dispatched the compact brief",
              "正文不超过 15 行" in prompt
              and "以下完成上报是协议步骤" not in prompt, prompt[:160])
    rc2, w, _, e2 = ctx.hao_json(
        ["wait", ctx.pane, "--token", (d or {}).get("token") or "",
         "--timeout", "120", "--json"])
    ctx.check("task completes", rc2 == 0 and (w or {}).get("status") == "done",
              e2)
    ctx.check("tier top", (d or {}).get("tier") == "top", d)


@scenario("custom_role_from_roles_md", "briefs", slow=False)
def custom_role_from_roles_md(ctx):
    tmp = tempfile.mkdtemp(prefix="hao-live-copy-")
    try:
        dst = os.path.join(tmp, "hao")
        shutil.copytree(SKILL_ROOT, dst)
        with open(os.path.join(dst, "references", "roles.md"), "a") as f:
            f.write("\n| `reliability-engineer` | mid | 实施 | 可靠性 |\n")
        copy_hao = os.path.join(dst, "scripts", "hao")
        env = dict(ctx.env)
        def run(args):
            return subprocess.run([sys.executable, copy_hao] + args,
                                  capture_output=True, text=True,
                                  timeout=120, env=env)
        p = run(["name", ctx.pane, "wren", "--role",
                 "reliability-engineer", "--json"])
        d = last_json(p.stdout) or {}
        ctx.check("copy name rc 0", p.returncode == 0, p.stderr)
        ctx.check("copy tier mid", d.get("tier") == "mid", d)
        p = run(["ask", ctx.pane, "只回答 custom-ok。", "--wait",
                 "--timeout", "120", "--json"])
        d = last_json(p.stdout) or {}
        ctx.check("copy ask rc 0", p.returncode == 0, p.stderr)
        ctx.check("copy ask tier mid", d.get("tier") == "mid", d)
        ctx.check("copy ask cap 40", d.get("max_lines") == 40, d)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        ctx.reset("moth", "reviewer")


# ---------------------------------------------------------------- waiting
@scenario("default_task_completes_with_result", "waiting")
def default_task_completes_with_result(ctx):
    rc, d, _, err = ctx.ask("只回答 default-ok。", timeout=120)
    ctx.check("ask rc 0", rc == 0, err)
    ctx.check("done", (d or {}).get("status") == "done", d)
    ctx.check("answer", ctx.answer(d, "default-ok"), d)


@scenario("long_task_is_waited", "waiting", slow=True)
def long_task_is_waited(ctx):
    start = time.time()
    rc, d, _, err = ctx.ask(
        "请先在 shell 执行命令 sleep 75（必须真的执行），命令结束后只回答一个词：slept",
        timeout=130)
    elapsed = time.time() - start
    ctx.check("ask rc 0", rc == 0, err)
    ctx.check("done", (d or {}).get("status") == "done", d)
    ctx.check("waited > 70s", elapsed > 70, round(elapsed, 1))
    ctx.check("answer", ctx.answer(d, "slept"), d)


@scenario("text_only_back_to_back", "waiting")
def text_only_back_to_back(ctx):
    ctx.settle()
    rc1, d1, _, e1 = ctx.hao_json(
        ["ask", ctx.pane, "只回答 text-one。", "--wait", "--text-only",
         "--timeout", "60", "--json"])
    ctx.check("first done", rc1 == 0 and (d1 or {}).get("status") == "done",
              e1)
    ctx.settle()
    start = time.time()
    rc2, d2, _, e2 = ctx.hao_json(
        ["ask", ctx.pane, "只回答 text-two。", "--wait", "--text-only",
         "--timeout", "60", "--json"])
    elapsed = time.time() - start
    ctx.check("second done", rc2 == 0 and (d2 or {}).get("status") == "done",
              e2)
    ctx.check("second under 20s", elapsed < 20, round(elapsed, 1))


@scenario("back_to_back_six_dispatches", "waiting", slow=True)
def back_to_back_six_dispatches(ctx):
    roles = ["arbiter", "reviewer", "developer", "reviewer",
             "developer", "arbiter"]
    names = ["moth", "hawk", "fern", "lens", "moss", "dove"]
    for i, (name, role) in enumerate(zip(names, roles), 1):
        rc, d, _, err = ctx.ask(f"只回答 six-{i}。", name=name,
                                role=role, timeout=120)
        ctx.check(f"dispatch {i} done",
                  rc == 0 and (d or {}).get("status") == "done", err)
        ctx.check(f"dispatch {i} tier",
                  (d or {}).get("tier") in
                  ({"arbiter": "top", "reviewer": "mid",
                    "developer": "low"}[role]), d)


@scenario("ledger_channel_hao_done", "waiting")
def ledger_channel_hao_done(ctx):
    ctx.settle()
    rc, d, _, err = ctx.hao_json(
        ["ask", ctx.pane, "只回答 ignored。", "--json", "--timeout", "60"])
    sid = (d or {}).get("shortid")
    ctx.check("async ask rc 0", rc == 0 and bool(sid), err)
    d2 = ctx.hao(["done", "--token", sid, "--summary",
                  "ledger answer", "--json"])
    ctx.check("done rc 0", d2.returncode == 0, d2.stderr)
    rc3, w, _, e3 = ctx.hao_json(
        ["wait", ctx.pane, "--token", sid, "--timeout", "10", "--json"])
    ctx.check("wait rc 0", rc3 == 0, e3)
    ctx.check("summary ledger", (w or {}).get("summary") == "ledger answer", w)


@scenario("lifecycle_mode_back_to_back", "waiting")
def lifecycle_mode_back_to_back(ctx):
    rc, d, _, err = ctx.ask("只回答 lifecycle-one。", timeout=120)
    ctx.check("first rc 0", rc == 0, err)
    rc2, d2, _, e2 = ctx.hao_json(
        ["ask", ctx.pane, "只回答 lifecycle-two。", "--mode", "lifecycle",
         "--wait", "--timeout", "120", "--json"])
    ctx.check("immediate lifecycle rc 0", rc2 == 0, e2)
    ctx.check("lifecycle done", (d2 or {}).get("status") == "done", d2)
    ctx.settle()
    rc3, d3, _, e3 = ctx.hao_json(
        ["ask", ctx.pane, "只回答 lifecycle-three。", "--mode", "lifecycle",
         "--wait", "--timeout", "120", "--json"])
    ctx.check("idle lifecycle rc 0", rc3 == 0, e3)


@scenario("lifecycle_requires_wait", "waiting")
def lifecycle_requires_wait(ctx):
    ctx.settle()
    p = ctx.hao(["ask", ctx.pane, "x", "--mode", "lifecycle"])
    ctx.check("rc 2", p.returncode == 2, p.returncode)
    ctx.check("mentions --wait", "--wait" in p.stderr, p.stderr)


@scenario("timeout_diagnostic_is_actionable", "waiting")
def timeout_diagnostic_is_actionable(ctx):
    ctx.settle()
    rc, d, _, err = ctx.hao_json(
        ["wait", ctx.pane, "--token", "beef11223344", "--timeout", "5",
         "--json"])
    text = err + json.dumps(d or {})
    ctx.check("rc 4", rc == 4, rc)
    ctx.check("no record message", "no ledger record was ever seen" in text,
              text)


@scenario("working_peer_is_not_read_at_high_frequency", "waiting", slow=True,
          isolate=True)
def working_peer_is_not_read_at_high_frequency(ctx):
    real = shutil.which("herdr")
    if not real:
        raise Skip("herdr not on PATH")
    wrap = tempfile.mkdtemp(prefix="hao-live-herdr-")
    log = os.path.join(wrap, "calls.log")
    try:
        script = os.path.join(wrap, "herdr")
        with open(script, "w") as f:
            f.write("#!/bin/sh\n"
                    "echo \"$@\" >> \"$HAO_LIVE_HERDR_LOG\"\n"
                    f"exec {real} \"$@\"\n")
        os.chmod(script, 0o700)
        ctx.settle()
        rc, d, _, err = ctx.hao_json(
            ["ask", ctx.pane,
             "请执行 shell 循环 60 次：每次 echo tick 后 sleep 1。结束后只回答 ticks。",
             "--json", "--timeout", "90"])
        sid = (d or {}).get("shortid")
        ctx.check("async ask", rc == 0 and bool(sid), err)
        env = dict(ctx.env)
        env["PATH"] = wrap + os.pathsep + env.get("PATH", "")
        env["HAO_LIVE_HERDR_LOG"] = log
        start = time.time()
        ctx.hao(["wait", ctx.pane, "--token", sid, "--timeout", "20",
                 "--json"], timeout=65, env=env)
        elapsed = max(1.0, time.time() - start)
        try:
            with open(log) as f:
                calls = [line for line in f if line.startswith(
                    ("pane read", "pane wait-output"))]
        except OSError:
            calls = []
        rate = len(calls) / elapsed
        ctx.check("pane reads <= 0.5/s", rate <= 0.5,
                  f"{len(calls)} calls in {elapsed:.1f}s ({rate:.2f}/s)")
        ctx.hao(["stop", ctx.pane], timeout=30)
        ctx.settle()
    finally:
        shutil.rmtree(wrap, ignore_errors=True)


@scenario("peer_status_transitions", "waiting")
def peer_status_transitions(ctx):
    ctx.settle()
    proc = subprocess.Popen(
        [sys.executable, HAO, "ask", ctx.pane, "只回答 transition-ok。",
         "--wait", "--timeout", "120", "--json"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=ctx.env)
    saw_working = False
    deadline = time.time() + 90
    while time.time() < deadline and proc.poll() is None:
        if ctx.agent_status() == "working":
            saw_working = True
            break
        time.sleep(0.25)
    out, err = proc.communicate(timeout=130)
    ctx.check("saw working", saw_working, "never observed working")
    ctx.check("ask rc 0", proc.returncode == 0, err)
    d = last_json(out) or {}
    ctx.check("done", d.get("status") == "done", d)


# ---------------------------------------------------------------- file
@scenario("file_mode_inline_result", "file")
def file_mode_inline_result(ctx):
    ctx.reset("fern", "developer")
    rc, d, _, err = ctx.hao_json(
        ["ask", ctx.pane, "42 加 0 等于多少？只回答数字。", "--mode", "file",
         "--wait", "--timeout", "120", "--json"])
    ctx.check("ask rc 0", rc == 0, err)
    ctx.check("done", (d or {}).get("status") == "done", d)
    ctx.check("tail non-empty", bool((d or {}).get("tail")), d)
    ctx.check("tail has 42", "42" in str((d or {}).get("tail")), d)
    ctx.check("result_consumed", (d or {}).get("result_consumed") is True, d)
    ctx.last_file_result = d or {}


@scenario("file_mode_zero_residue", "file")
def file_mode_zero_residue(ctx):
    d = ctx.last_file_result or {}
    rp = d.get("result_path")
    ctx.check("result_path retained", bool(rp), d)
    if rp:
        ctx.check("result file gone", not os.path.exists(rp), rp)
        ctx.check("result dir gone",
                  not os.path.exists(os.path.dirname(rp)), rp)
        # scoped to this task: other scenarios may legitimately have a
        # running record of their own in the shared state dir
        sid = os.path.basename(os.path.dirname(rp))
        left = [f for f in ctx.state_files() if sid in f]
        ctx.check("no record or lock left for this task", not left, left)


@scenario("stale_record_is_cleaned", "file")
def stale_record_is_cleaned(ctx):
    tab, pane = ctx.new_instance("pi", "hao-live-stale")
    try:
        rc, d, _, err = ctx.hao_json(
            ["ask", pane, "请执行 shell 命令 sleep 60（必须真的执行），结束后回答 slept。",
             "--json", "--timeout", "90"])
        ctx.check("async ask", rc == 0 and bool((d or {}).get("shortid")), err)
        ctx.close_tab(tab)
        time.sleep(2)
        rc2, c, _, e2 = ctx.hao_json(["clean", "--all", "--json"])
        ctx.check("clean rc 0", rc2 == 0, e2)
        ctx.check("removed >= 1", (c or {}).get("removed", 0) >= 1, c)
        ctx.check("state gone", not os.path.exists(ctx.state), ctx.state)
    finally:
        ctx.close_tab(tab)


@scenario("result_missing_task_exits_3", "file")
def result_missing_task_exits_3(ctx):
    rc, d, _, err = ctx.hao_json(["result", "beef11223344", "--json"])
    ctx.check("rc 3", rc == 3, rc)
    ctx.check("error shape", (d or {}).get("ok") is False, d)


# ---------------------------------------------------------------- control
@scenario("cancel_keeps_peer_running", "control", isolate=True)
def cancel_keeps_peer_running(ctx):
    ctx.settle()
    rc, d, _, err = ctx.hao_json(
        ["ask", ctx.pane, "请执行 shell 命令 sleep 60（必须真的执行）。",
         "--json", "--timeout", "90"])
    sid = (d or {}).get("shortid")
    ctx.check("async ask", rc == 0 and bool(sid), err)
    for _ in range(30):     # the peer needs a moment to pick the task up
        if ctx.agent_status() == "working":
            break
        time.sleep(0.5)
    rc2, c, _, e2 = ctx.hao_json(["cancel", sid, "--json"])
    ctx.check("cancel rc 0", rc2 == 0, e2)
    ctx.check("peer_running", (c or {}).get("peer_running") is True, c)
    ctx.check("next abort", "abort" in str((c or {}).get("next")), c)
    ctx.check("still working", ctx.agent_status() == "working",
              ctx.agent_status())
    ctx.hao(["abort", sid, "--interrupt", "--json"], timeout=60)
    ctx.settle()


@scenario("abort_interrupts", "control", isolate=True)
def abort_interrupts(ctx):
    ctx.settle()
    rc, d, _, err = ctx.hao_json(
        ["ask", ctx.pane, "请执行 shell 命令 sleep 60（必须真的执行）。",
         "--json", "--timeout", "90"])
    sid = (d or {}).get("shortid")
    ctx.check("async ask", rc == 0 and bool(sid), err)
    rc2, a, _, e2 = ctx.hao_json(["abort", sid, "--interrupt", "--json"])
    ctx.check("abort rc 0", rc2 == 0, e2)
    ctx.check("interrupted", (a or {}).get("interrupted") is True, a)
    ctx.settle(20)


@scenario("stop_working_peer", "control", isolate=True)
def stop_working_peer(ctx):
    ctx.settle()
    rc, d, _, err = ctx.hao_json(
        ["ask", ctx.pane, "请执行 shell 命令 sleep 60（必须真的执行）。",
         "--json", "--timeout", "90"])
    ctx.check("async ask", rc == 0, err)
    for _ in range(20):
        if ctx.agent_status() == "working":
            break
        time.sleep(0.5)
    rc2, s, _, e2 = ctx.hao_json(["stop", ctx.pane, "--json"])
    ctx.check("stop rc 0", rc2 == 0, e2)
    ctx.check("sent keys", bool((s or {}).get("sent")), s)
    deadline = time.time() + 5
    while time.time() < deadline and ctx.agent_status() == "working":
        time.sleep(0.3)
    ctx.check("not working", ctx.agent_status() != "working",
              ctx.agent_status())
    rc3, s2, _, _ = ctx.hao_json(["stop", ctx.pane, "--json"])
    ctx.check("second stop empty", rc3 == 0 and (s2 or {}).get("sent") == [],
              s2)


@scenario("stop_dry_run_sends_nothing", "control", isolate=True)
def stop_dry_run_sends_nothing(ctx):
    ctx.settle()
    ctx.hao_json(["ask", ctx.pane, "请执行 shell 命令 sleep 60（必须真的执行）。",
                  "--json", "--timeout", "90"])
    for _ in range(20):
        if ctx.agent_status() == "working":
            break
        time.sleep(0.5)
    rc, s, _, err = ctx.hao_json(["stop", ctx.pane, "--dry-run", "--json"])
    ctx.check("stop rc 0", rc == 0, err)
    ctx.check("dry_run true", (s or {}).get("dry_run") is True, s)
    ctx.check("still working", ctx.agent_status() == "working",
              ctx.agent_status())
    ctx.hao_json(["stop", ctx.pane, "--json"])
    ctx.settle()


@scenario("say_sends_plain_prompt", "control")
def say_sends_plain_prompt(ctx):
    ctx.settle()
    before = len(ctx.state_files())
    rc, d, _, err = ctx.hao_json(["say", ctx.pane, "只回答 say-ok。", "--json"])
    ctx.check("say rc 0", rc == 0, err)
    ctx.settle(40)
    ctx.check("no task record", len(ctx.state_files()) <= before,
              (before, ctx.state_files()))


@scenario("say_strict_refuses_working", "control", isolate=True)
def say_strict_refuses_working(ctx):
    ctx.settle()
    ctx.hao_json(["ask", ctx.pane, "请执行 shell 命令 sleep 60（必须真的执行）。",
                  "--json", "--timeout", "90"])
    for _ in range(20):
        if ctx.agent_status() == "working":
            break
        time.sleep(0.5)
    rc, _, _, err = ctx.hao_json(["say", ctx.pane, "x", "--strict", "--json"])
    ctx.check("rc 6", rc == 6, rc)
    ctx.check("refuses", "working" in err, err)
    ctx.hao_json(["stop", ctx.pane, "--json"])
    ctx.settle()


# ---------------------------------------------------------------- restore
@scenario("restore_after_name_cleared", "restore")
def restore_after_name_cleared(ctx):
    ctx.reset("moth", "reviewer")
    ctx.herdr(["agent", "rename", ctx.pane, "--clear"])
    p = ctx.hao(["restore", "--dry-run", "--pick", ctx.pane])
    expected = f"would restore name moth (role reviewer) on {ctx.pane}"
    ctx.check("dry-run line", expected in p.stdout, p.stdout)
    rc, d, _, err = ctx.hao_json(["restore", "--pick", ctx.pane, "--json"])
    ctx.check("restore rc 0", rc == 0, err)
    ctx.check("restored 1", (d or {}).get("restored") == 1, d)
    rc2, s, _, _ = ctx.hao_json(["status", ctx.pane, "--json"])
    ctx.check("name moth", (s or {}).get("name") == "moth", s)
    ctx.check("label kept", (s or {}).get("label") == "hao-moth-reviewer", s)


@scenario("restore_all_dry_run", "restore")
def restore_all_dry_run(ctx):
    rc, d, _, err = ctx.hao_json(["restore", "--all", "--dry-run", "--json"])
    ctx.check("rc 0", rc == 0, err)


@scenario("clear_dry_run_changes_nothing", "restore")
def clear_dry_run_changes_nothing(ctx):
    ctx.reset("moss", "developer")
    rc, d, _, err = ctx.hao_json(["clear", ctx.pane, "--dry-run", "--json"])
    ctx.check("rc 0", rc == 0, err)
    q = ctx.herdr_json(["pane", "get", ctx.pane])[1] or {}
    label = ((q.get("result") or {}).get("pane") or {}).get("label")
    ctx.check("label unchanged", label == "hao-moss-developer", label)


@scenario("clear_removes_label", "restore")
def clear_removes_label(ctx):
    ctx.reset("dove", "developer")
    rc, d, _, err = ctx.hao_json(["clear", ctx.pane, "--json"])
    ctx.check("rc 0", rc == 0, err)
    q = ctx.herdr_json(["pane", "get", ctx.pane])[1] or {}
    label = ((q.get("result") or {}).get("pane") or {}).get("label")
    ctx.check("label empty", not label, label)
    rc2, s, _, _ = ctx.hao_json(["status", ctx.pane, "--json"])
    ctx.check("name null", (s or {}).get("name") is None, s)


# ---------------------------------------------------------------- read-only
@scenario("doctor_reports_environment", "readonly")
def doctor_reports_environment(ctx):
    rc, d, _, err = ctx.hao_json(["doctor", "--json"])
    ctx.check("rc 0", rc == 0, err)
    ctx.check("ok true", (d or {}).get("ok") is True, d)


@scenario("read_only_commands_create_no_state", "readonly")
def read_only_commands_create_no_state(ctx):
    ctx.hao(["clean", "--all"], timeout=60)
    for args in (["list", "--json"], ["status", ctx.pane, "--json"],
                 ["restore", "--dry-run", "--json"],
                 ["suggest", "review", "--json"],
                 ["clean", "--dry-run", "--json"]):
        p = ctx.hao(args)
        ctx.check("rc 0: " + args[0], p.returncode == 0, p.stderr)
    ctx.check("state still absent", not os.path.exists(ctx.state), ctx.state)


@scenario("draft_in_input_box_is_consumed", "dispatch")
def draft_in_input_box_is_consumed(ctx):
    ctx.settle()
    ctx.reset("fern", "developer")
    # A plausible half-typed line. The draft is glued in front of the task,
    # so its wording reaches the model: text that reads like a label
    # ("UNSENT DRAFT") can make a weak model refuse the task as "not sent".
    draft = "顺便看一下"
    ctx.herdr(["pane", "send-text", ctx.pane, draft])
    rc, d, _, err = ctx.hao_json(
        ["ask", ctx.pane, "只回答 draft-ok。", "--wait", "--timeout", "120",
         "--json"])
    ctx.check("ask rc 0", rc == 0, err)
    ctx.check("done", (d or {}).get("status") == "done", d)
    ctx.settle()
    time.sleep(1)       # pi still shows its "Working" banner right after the wait
    box = ctx.input_box_text()
    if box is not None:
        ctx.check("input box no longer holds the draft", draft not in box, box)
    # when the echo is still on screen, the draft sits right in front of the
    # task; pi sometimes clears the screen, so this is observed when possible
    flat = ctx.pane_flat(400)
    if draft in flat:
        ctx.check("draft glued in front of the task", draft + "[TASK" in flat)


@scenario("claude_code_peer_end_to_end", "cross-agent")
def claude_code_peer_end_to_end(ctx):
    if "claude" not in ctx.kinds:
        raise Skip("claude not selected by --kinds")
    if not shutil.which("claude"):
        raise Skip("claude not on PATH")
    tab, pane = ctx.new_instance("claude", "hao-live-claude", wait=45)
    try:
        rc, d, _, err = ctx.hao_json(
            ["name", pane, "moth", "--role", "arbiter", "--json"])
        ctx.check("name rc 0", rc == 0, err)
        # A fresh Claude Code instance spends its first turn on start-up and
        # on reading the hao script before it trusts `hao done`: measured 43s
        # to its first token in the afternoon and 69s in the evening. Warm it
        # up with a plain prompt first, then dispatch the measured task.
        ctx.hao_json(["say", pane, "只回答 ready。", "--json"])
        for _ in range(60):          # dispatching is not the peer starting
            if ctx.agent_status(pane) == "working":
                break
            time.sleep(0.5)
        deadline = time.time() + 240
        while time.time() < deadline:
            if ctx.agent_status(pane) in ("idle", "done"):
                break
            time.sleep(1)
        rc2, a, _, e2 = ctx.hao_json(
            ["ask", pane, "只回答 claude-ok。", "--wait",
             "--timeout", "300", "--json"])
        ctx.check("ask rc 0", rc2 == 0, e2)
        ctx.check("done", (a or {}).get("status") == "done", a)
        ctx.check("tier top", (a or {}).get("tier") == "top", a)
        ctx.check("answer", ctx.answer(a, "claude-ok"), a)
    finally:
        ctx.close_tab(tab)


@scenario("sentinel_split_by_hyphen_is_accepted", "waiting")
def sentinel_split_by_hyphen_is_accepted(ctx):
    tab, pane = ctx.new_instance(kind=None, label="hao-live-shell")
    sid = "5e1f0a2b3c4d"
    token = "hao-" + "5e1f0a2b" + "3c4d9a7b"
    split = "hao-" + "5e1f0a2b" + "-" + "3c4d9a7b"
    sid2 = "5e1f0a2b3c4e"
    token2 = "hao-" + "5e1f0a2b" + "3c4e9a7b"
    wait = None
    try:
        ctx.seed_running(sid, token, pane)
        wait = subprocess.Popen(
            [sys.executable, HAO, "wait", pane, "--token", token,
             "--no-agent", "--timeout", "15", "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=ctx.env)
        time.sleep(2)
        start = time.time()
        p = ctx.herdr(["pane", "run", pane,
                       "printf 'answer\\nHAO_DONE " + split + "\\n'"],
                      timeout=15)
        ctx.check("pane run rc 0", p.returncode == 0,
                  (p.stderr or p.stdout)[:200])
        out, err = wait.communicate(timeout=20)
        elapsed_after_print = time.time() - start
        d = last_json(out) or {}
        ctx.check("fast path within 8s", elapsed_after_print < 8,
                  round(elapsed_after_print, 1))
        ctx.check("wait rc 0", wait.returncode == 0, err)
        ctx.check("done", d.get("status") == "done", d)
        ctx.check("raw matched_line",
                  split in str(d.get("matched_line")), d)
        # a shell pane also shows its prompt and the command echo before the
        # answer (and that echo contains the sentinel text), so assert on
        # where the tail ends: the sentinel line itself is excluded
        tail_lines = [l for l in str(d.get("tail") or "").splitlines() if l.strip()]
        ctx.check("tail ends with the answer, sentinel line excluded",
                  bool(tail_lines) and tail_lines[-1].strip() == "answer",
                  tail_lines[-1:] or d)

        ctx.consume_record(sid)
        sid3 = "5e1f0a2b3c4f"
        token3 = "hao-" + "5e1f0a2b" + "3c4f9a7b"

        def reject(name, sid_n, token_n, line):
            """Print a malformed sentinel for a seeded task: the wait must
            not accept it. This exercises the herdr-side regex, which the
            unit tests cannot."""
            ctx.seed_running(sid_n, token_n, pane)
            w = subprocess.Popen(
                [sys.executable, HAO, "wait", pane, "--token", token_n,
                 "--no-agent", "--timeout", "8", "--json"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=ctx.env)
            try:
                time.sleep(2)
                ctx.herdr(["pane", "run", pane,
                           "printf 'nope\\nHAO_DONE " + line + "\\n'"],
                          timeout=15)
                out_n, _ = w.communicate(timeout=30)
                d_n = last_json(out_n) or {}
                ctx.check(name, w.returncode == 4 and d_n.get("status") != "done",
                          (w.returncode, str(d_n.get("error") or d_n)[:110]))
            finally:
                if w.poll() is None:
                    w.kill()
                    w.communicate()
                ctx.consume_record(sid_n)

        reject("wrong second half is rejected", sid2, token2,
               "hao-5e1f0a2b-3c4dffff")
        reject("space-separated halves are rejected", sid3, token3,
               "hao-5e1f0a2b 3c4f9a7b")
    finally:
        if wait and wait.poll() is None:
            wait.kill()
            wait.communicate()
        ctx.consume_record(sid)
        ctx.consume_record(sid2)
        ctx.consume_record(sid3)
        ctx.close_tab(tab)


@scenario("suite_leaves_zero_residue", "cleanup")
def suite_leaves_zero_residue(ctx):
    ctx.check("state dir absent", not os.path.exists(ctx.state), ctx.state)
    ctx.check("no extra tabs", not ctx.extra_tabs, ctx.extra_tabs)


# ---------------------------------------------------------------- runner
def select(args):
    chosen = []
    for s in SCENARIOS:
        if s.name == "suite_leaves_zero_residue":
            continue
        if args.filter and args.filter.lower() not in s.name.lower():
            continue
        if args.quick and s.slow:
            continue
        chosen.append(s)
    return chosen


def setup(ctx):
    q = ctx.herdr_json(["pane", "list", "--workspace", ctx.workspace])
    if q[0] != 0:
        return "herdr pane list failed: " + (q[3] or "").strip()[:200]
    p = ctx.herdr(["tab", "create", "--workspace", ctx.workspace,
                   "--cwd", "/tmp", "--label", "hao-live", "--no-focus"])
    if p.returncode != 0:
        return "tab create failed: " + p.stderr.strip()[:200]
    data = last_json(p.stdout) or {}
    res = data.get("result") or {}
    ctx.tab = res.get("tab_id") or (res.get("tab") or {}).get("tab_id")
    if not ctx.tab:
        return "tab create returned no tab_id"
    for _ in range(20):
        q = ctx.herdr_json(["pane", "list", "--workspace", ctx.workspace])
        for row in ((q[1] or {}).get("result") or {}).get("panes", []):
            if row.get("tab_id") == ctx.tab:
                ctx.pane = row.get("pane_id")
                break
        if ctx.pane:
            break
        time.sleep(0.25)
    if not ctx.pane:
        return "no pane found in new tab"
    a = ctx.herdr(["agent", "start", ctx.agent_name(), "--kind", "pi",
                   "--pane", ctx.pane, "--timeout", "60000"], timeout=75)
    if a.returncode != 0:
        return "agent start failed: " + (a.stderr or a.stdout).strip()[:200]
    time.sleep(6)
    return None


def _run_isolated(ctx, sc):
    """Run sc against a throwaway instance, then destroy it.

    ctx.pane / ctx.tab point at the throwaway for the duration; afterwards
    the tab is closed, the shared peer is restored and the suite's ledger is
    cleaned (records of the destroyed instance are orphans)."""
    tab, pane = ctx.new_instance("pi", "hao-live-iso")
    main_pane, main_tab = ctx.pane, ctx.tab
    ctx.pane, ctx.tab = pane, tab
    try:
        sc.fn(ctx)
    finally:
        ctx.close_tab(tab)
        ctx.pane, ctx.tab = main_pane, main_tab
        ctx.hao_json(["clean", "--all", "--json"])


def run_one(ctx, sc):
    start = time.time()
    ctx.checks = []
    status, detail = "PASS", ""
    try:
        if sc.isolate:
            _run_isolated(ctx, sc)
        else:
            sc.fn(ctx)
        if not all(ok for ok, _, _ in ctx.checks):
            status = "FAIL"
    except Skip as e:
        status, detail = "SKIP", str(e)
    except Exception:
        status = "FAIL"
        detail = traceback.format_exc()[-1200:]
    elapsed = time.time() - start
    print(f"{status:4} {sc.name} ({elapsed:.1f}s)")
    for ok, desc, extra in ctx.checks:
        print(f"     {'ok' if ok else 'FAIL'} {desc}"
              + (f": {extra}" if extra and not ok else ""))
    if detail:
        print("     " + detail.replace("\n", "\n     "))
    return status, elapsed


def cleanup(ctx):
    for tab in list(ctx.extra_tabs):
        try:
            ctx.herdr(["tab", "close", tab], timeout=20)
        except Exception:
            pass
    if ctx.tab:
        try:
            ctx.herdr(["tab", "close", ctx.tab], timeout=20)
        except Exception:
            pass
    try:
        ctx.hao(["clean", "--all"], timeout=60)
    except Exception:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="hao optional live scenario suite")
    ap.add_argument("--filter", default="")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--kinds", default=DEFAULT_KINDS)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for s in SCENARIOS:
            suffix = " [slow]" if s.slow else ""
            print(f"{s.name}\t{s.group}{suffix}")
        print(f"{len(SCENARIOS)} scenarios")
        return 0

    workspace = os.environ.get("HERDR_WORKSPACE_ID")
    if os.environ.get("HERDR_ENV") != "1" or not workspace:
        print("run_live: requires HERDR_ENV=1 and HERDR_WORKSPACE_ID",
              file=sys.stderr)
        return 2
    if not shutil.which("herdr"):
        print("run_live: herdr not found on PATH", file=sys.stderr)
        return 2
    try:
        probe = subprocess.run(["herdr", "pane", "list", "--workspace",
                                workspace], capture_output=True, text=True,
                               timeout=15)
    except Exception as e:
        print(f"run_live: herdr unreachable: {e}", file=sys.stderr)
        return 2
    if probe.returncode != 0:
        print("run_live: herdr pane list failed: "
              + (probe.stderr or "").strip()[:200], file=sys.stderr)
        return 2

    kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}
    tmp = tempfile.mkdtemp(prefix="hao-live-suite-")
    state = os.path.join(tmp, "state", "tasks")
    ctx = Ctx(workspace, state, kinds, args.quick)
    chosen = select(args)
    results = []
    setup_err = setup(ctx) if chosen else None
    try:
        if setup_err:
            print("SKIP setup: " + setup_err)
            for sc in chosen:
                print(f"SKIP {sc.name} (setup failed)")
                results.append(("SKIP", 0.0))
        else:
            for sc in chosen:
                results.append(run_one(ctx, sc))
    finally:
        cleanup(ctx)
    # 44 always runs, even with --filter / --quick.
    residue = next(s for s in SCENARIOS
                   if s.name == "suite_leaves_zero_residue")
    ctx.checks = []
    ctx.extra_tabs = []
    status, _ = run_one(ctx, residue)
    results.append((status, 0.0))
    counts = {k: sum(1 for s, _ in results if s == k)
              for k in ("PASS", "FAIL", "SKIP")}
    print(f"summary: {counts['PASS']} PASS, {counts['FAIL']} FAIL, "
          f"{counts['SKIP']} SKIP")
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
