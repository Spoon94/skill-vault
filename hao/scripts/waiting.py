# Waiting kernel for the hao skill: ask/wait/done completion, the sentinel
# matcher, tail extraction and the three wait modes (sentinel/lifecycle/file).
#
# This file is exec-included by hao/scripts/hao (see _include_waiting there):
# it is a PHYSICAL split for readability, not an independent module. All
# functions and constants here land in the hao module namespace and can use
# its imports (re, json, os, sys, time) and its helpers (run_herdr,
# herdr_error_rc, _herdr_err_code, _load_module, normalize_id, current_state,
# _set_error, fail, _json_out, ...) directly, exactly as before the split.
# Tests keep patching hao.<name>; the offline guard keeps intercepting
# hao.run_herdr. Do not import this file as a standalone module.
#
# Split point: everything related to waiting for task completion lives here;
# dispatch (build_prompt/cmd_ask), naming/restore, control (cancel/abort/stop)
# and the CLI stay in hao/scripts/hao.

_PREFIX_CHARS = r"⏺●✻│⎿`>*+\-•·#┃┆┇┊┄┈─━└┘✓✔"

_TAIL_CHARS = r"\s.。!！│`*|┃┆┇┊┄┈─━└┘✓✔"

SENTINEL_RE = re.compile(
    rf"^\s*(?:[{_PREFIX_CHARS}]|\d+\.|\|)*\s*HAO_DONE:?\s+((?:hao-)?[0-9a-f]{{12,32}})[{_TAIL_CHARS}]*$")

_LEDGER_WARNED = False
_WAIT_PANE = None

def _timeout_detail(observed_working, last_status, timeout, seen_record=True,
                    pane=None):
    if not seen_record:
        return (f"timeout after {timeout}s; no ledger record was ever seen "
                f"for this task (not dispatched via hao ask, already consumed, "
                f"or expired — check HAO_STATE_DIR); only the text sentinel "
                f"was watched")
    state = last_status or "unknown"
    if observed_working:
        tail = f"agent_status={state}, observed working since dispatch"
    else:
        tail = (f"agent_status={state}, never observed working since dispatch "
                f"— peer may have skipped the completion protocol")
    if pane:
        tail += f"; inspect with: herdr pane read {pane}"
    return f"timeout after {timeout}s; {tail}"

def _wait_timeout(observed_working, last_status, timeout, seen_record):
    global _WAIT_DIAG
    _WAIT_DIAG = _timeout_detail(observed_working, last_status, timeout,
                                 seen_record=seen_record, pane=_WAIT_PANE)
    return 4

def _ledger_warn(err):
    """One-time stderr warning when the ledger is unusable (graceful
    degradation: pane evidence stays authoritative)."""
    global _LEDGER_WARNED
    if not _LEDGER_WARNED:
        print(f"hao: warning: ledger unavailable ({err}); "
              f"degrading to pane evidence", file=sys.stderr)
        _LEDGER_WARNED = True

def _safe_get(l, sid):
    try:
        return l.get(sid)
    except Exception:
        return None

def _wait_round_rec(l, sid):
    """Fresh record for this wait round: heartbeat (locked read+merge+write)
    with read-only fallback. Ledger unavailable must never kill a wait —
    pane sentinel evidence stays authoritative (graceful degradation)."""
    try:
        rec = l.heartbeat(sid)
        return rec if rec is not None else {}
    except Exception as e:
        _ledger_warn(e)
        rec = _safe_get(l, sid)
        return rec if rec is not None else {}

def _wait_record_gone(l, sid):
    """True only when the ledger is readable and the record is now absent."""
    try:
        return l.get(sid) is None
    except Exception:
        return False

def _wait_consumed(l, sid, seen):
    if seen and _wait_record_gone(l, sid):
        _set_error("task record already consumed")
        return True
    return False

def _deadline_passed(deadline):
    return deadline is not None and time.time() >= deadline

def _wait_common_check(rec):
    """Returns (kind, payload): 'done'/'cancelled'/None. rec = fresh heartbeat read."""
    if rec and rec.get("status") == "done":
        return "done", {"status": "done", "result_path": rec.get("result_path"),
                        "summary": rec.get("summary"), "matched_line": rec.get("matched_line")}
    if rec and rec.get("status") == "cancelled":
        return "cancelled", None
    return None, None

def _agent_status_gate(pane, machine, no_agent, accept_unknown,
                       unknown_code=9):
    """One agent get per wait round; returns (code, status, agent_obj)."""
    if no_agent:
        return None, None, None
    rc, out, err = run_herdr(["agent", "get", pane], machine)
    if rc != 0:
        if _herdr_err_code(err) == "agent_not_found":
            _set_error(f"agent {pane} not found; for a shell pane use --no-agent (or --mode file)")
            return 3, None, None
        return herdr_error_rc(err, 8), None, None
    try:
        ag = json.loads(out)["result"]["agent"]
        st = ag.get("agent_status")
    except Exception:
        return fail(8, f"herdr returned invalid JSON for agent {pane}"), None, None
    if st == "blocked":
        return 5, st, ag
    if st in ("exited", "closed"):
        return 3, st, ag
    if st == "unknown" and not accept_unknown:
        _set_error(f"agent {pane} status unknown; add --accept-unknown")
        return unknown_code, st, ag
    return None, st, ag

def _agent_gate(pane, machine, no_agent, accept_unknown):
    """Compatibility wrapper: exit code only (tests/legacy callers)."""
    code, _status, _agent = _agent_status_gate(
        pane, machine, no_agent, accept_unknown)
    return code

def _token_matches(matched, token, sid, joined=False):
    """matched: token text from the pane; the hao- prefix is optional (a
    live peer dropped it once). Accept the exact token, or a bare 12-hex
    shortid prefix. Over-long (>16-hex) matches — the observed segment-
    duplication corruption — additionally require head-8 AND tail-8 of the
    KNOWN full token: a shortid anchor alone would let a truncated sentinel
    plus an unrelated hex line fake a completion (r9#1). Without the full
    token (degraded ledger) over-long never matches: prefer the miss.

    joined=True marks a line REASSEMBLED from wrapped fragments (r13#1):
    only the exact full token (or an over-long passing head-8/tail-8)
    authenticates it — a shortid anchor is not proof for a line the pane
    never contained verbatim."""
    hexpart = matched[4:] if matched.startswith("hao-") else matched
    bare = None
    if token:
        bare = token[4:] if token.startswith("hao-") else token
    if joined:
        if not bare or len(bare) < 16:
            return False
        if hexpart == bare:
            return True
        return (len(hexpart) > 16 and hexpart[:8] == bare[:8]
                and hexpart[-8:] == bare[-8:])
    if bare and hexpart == bare:
        return True
    if len(hexpart) > 16:
        return bool(bare) and len(bare) >= 16 \
            and hexpart[:8] == bare[:8] and hexpart[-8:] == bare[-8:]
    if len(hexpart) == 12:
        # forge r14 exception: a bare 12-hex shortid sentinel is acceptable
        if sid and hexpart == sid[:12]:
            return True
        return bool(bare) and hexpart == bare[:12]
    # 13-16 hex (r14#2): require the full token — exact for 16, its prefix
    # for 13-15 truncated renderings; a shortid anchor alone would accept
    # sid+4 fabricated hex. Waits normally hold the full token (ledger
    # upgrade each round); a bare-shortid wait prefers the miss.
    return bool(bare) and len(bare) >= 16 and hexpart == bare[:len(hexpart)]

def _sentinel_check(pane, token, sid, machine):
    """Quick probe; returns (matched_line | None, error_rc | None, stale).

    stale=True means wait-output matched a sentinel line that belongs to
    another task; the caller should rescan the tail for the current one."""
    rc, out, err = run_herdr(
        ["pane", "wait-output", pane, "--regex", SENTINEL_RE.pattern, "--timeout", "1000"],
        machine)
    if rc != 0:
        if _herdr_err_code(err) == "timeout":
            return None, None, False  # normal "not yet"
        return None, herdr_error_rc(err, 8), False
    try:
        ml = json.loads(out).get("result", {}).get("matched_line", "") or ""
    except Exception:
        ml = out
    m = SENTINEL_RE.search(ml)
    if not m:
        return None, None, False
    if _token_matches(m.group(1), token, sid):
        return ml, None, False
    return None, None, True

_PREFIX_LINE_RE = re.compile(
    rf"^(?P<head>\s*(?:[{_PREFIX_CHARS}]|\d+\.|\|)*\s*HAO_DONE[{_TAIL_CHARS}]*)"
    rf"(?P<pre>hao-)?(?P<frag>[0-9a-f]{{0,11}})(?P<tail>[{_TAIL_CHARS}]*)$")

_HEX_CONT_RE = re.compile(
    rf"^\s*(?:[{_PREFIX_CHARS}]|\|)*\s*(hao-)?([0-9a-f]{{1,32}})[{_TAIL_CHARS}]*$")

def _join_wrapped_sentinels(lines):
    """Rejoin sentinels split by narrow-pane wrapping (r8#1/r10-r14).

    Returns a list of (line, joined) tuples — the joined flag explicitly
    marks lines REASSEMBLED from fragments; callers must never infer it
    from string identity (r14#1).

    Only a STANDALONE sentinel-prefix line may absorb a continuation —
    the same left anchor and decorations SENTINEL_RE accepts, so prompt
    echoes like "…打印：HAO_DONE" never join. Shapes:
    - keyword line already carrying hao- and/or <12 hex absorbs a bare-hex
      continuation while the joined token stays <=32 hex (chains across
      multiple wraps); head decorations are stripped and trailing
      decorations kept after the insertion point (r12#2/r13#2);
    - keyword-only line absorbs a following COMPLETE token line — >=16
      hex with or without the hao- prefix (r12#1);
    - a complete sentinel is never extended.
    Rejoined candidates must still pass _token_matches(joined=True)."""
    out = []  # [line, joined]
    for line in lines:
        if out:
            pm = _PREFIX_LINE_RE.match(out[-1][0])
            if pm:
                c = _HEX_CONT_RE.match(line)
                if c:
                    pre, cont = c.group(1), c.group(2)
                    if pm.group("pre") or pm.group("frag"):
                        if not pre and len(pm.group("frag")) + len(cont) <= 32:
                            head = re.sub(r"[:\s.。!！│`*|]+$", "",
                                          pm.group("head").rstrip())
                            out[-1] = [head + " " + (pm.group("pre") or "")
                                       + pm.group("frag") + cont
                                       + pm.group("tail"), True]
                            continue
                    elif len(cont) >= 16:
                        kw = re.sub(r"[:\s.。!！│`*|]+$", "",
                                    pm.group("head").rstrip())
                        out[-1] = [kw + " " + (pre or "") + cont, True]
                        continue
        out.append([line, False])
    return [(l, j) for l, j in out]

_LAST_PANE_TEXT = None

_TUI_BORDERS = set("│┃┆┇┊┄┈─━└┘|╎╏")

_TUI_MARKERS = set("●⏺✻▸▶")

_TAIL_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)")

def _strip_tui_line(line):
    line = _TAIL_ANSI_RE.sub("", line)
    line = "".join(ch for ch in line if ch >= " " and ch != "\x7f").strip()
    while line and line[0] in _TUI_BORDERS:
        line = line[1:].lstrip()
    while line and line[-1] in _TUI_BORDERS:
        line = line[:-1].rstrip()
    if line[:1] in _TUI_MARKERS:
        line = line[1:].lstrip()
    return line

_PROTOCOL_ECHO_PREFIXES = (
    "以下完成上报", "完成时，将令牌", "完成顺序：", "首选完成上报",
    "同时在最终消息", "只有确认下面", "若无法执行", "——台账副作用",
    "请先把最终结果", "不要调用任何命令",
)

def _is_harness_noise(raw, cleaned):
    low = cleaned.lower()
    if cleaned.startswith(_PROTOCOL_ECHO_PREFIXES):
        return True
    if low.startswith("thought for") or low.startswith("update available"):
        return True
    if raw.lstrip()[:1] in set("✻●⏺") and " for " in low:
        return True
    if not cleaned:
        return True
    if re.fullmatch(r"[-─━═_=]{3,}", cleaned):
        return True
    return cleaned in (">", "❯", "$", "%")

def _set_blocked_hint(pane):
    _set_error(f"agent {pane} is blocked; peer may be approval-gated: "
               f"ask the user to approve that command once, or re-dispatch "
               f"with: hao ask {pane} \"<task>\" --text-only")

_MATCH_DECO = set("-*+•·>#>") | _TUI_BORDERS | _TUI_MARKERS

_MATCH_TAIL = _TUI_BORDERS | _TUI_MARKERS | set("✓✔")

def _normalize_for_match(line):
    line = _strip_tui_line(line)
    return re.sub(r"[\s" + re.escape("".join(sorted(_MATCH_DECO | _MATCH_TAIL))) + r"]+", "", line)

def _prompt_end_line(lines, prompt):
    if not prompt:
        return None
    norm_prompt = "".join(_normalize_for_match(line)
                          for line in prompt.splitlines())
    if not norm_prompt:
        return None
    chars = []
    line_ids = []
    for i, line in enumerate(lines):
        norm = _normalize_for_match(line)
        chars.append(norm)
        line_ids.extend([i] * len(norm))
    norm_pane = "".join(chars)
    pos = norm_pane.rfind(norm_prompt)
    if pos < 0:
        return None
    return line_ids[pos + len(norm_prompt) - 1]

def _tail_from_pane_text(text, token, sid, prompt=None):
    """Answer text: after the prompt echo (if visible) and before sentinel."""
    lines = text.splitlines()
    start = None
    for k in range(1, min(len(lines), 8) + 1):
        for line, joined in _join_wrapped_sentinels(lines[-k:]):
            m = SENTINEL_RE.match(line)
            if m and _token_matches(m.group(1), token, sid, joined=joined):
                start = len(lines) - k
                break
        if start is not None:
            break
    if start is None:
        for i in range(len(lines) - 1, -1, -1):
            m = SENTINEL_RE.match(lines[i])
            if m and _token_matches(m.group(1), token, sid):
                start = i
                break
    if start is None:
        return None
    prompt_end = _prompt_end_line(lines, prompt)
    if prompt_end is not None and prompt_end < start:
        raw = lines[prompt_end + 1:start]
    else:
        raw = lines[:start]
        cleaned = [_strip_tui_line(line) for line in raw]
        last_task = None
        for i, line in enumerate(cleaned):
            if "--- 任务结束 ---" in line:
                last_task = i
        if last_task is not None:
            raw = raw[last_task + 1:]
            cleaned = cleaned[last_task + 1:]
    cleaned = [_strip_tui_line(line) for line in raw]
    cleaned = [line for line, orig in zip(cleaned, raw)
               if not _is_harness_noise(orig, line)]
    while cleaned and not cleaned[0]:
        cleaned.pop(0)
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    tail = "\n".join(cleaned[-40:])
    return tail[-2000:] if len(tail) > 2000 else tail

def _completion_tail(pane, token, sid, machine, prompt=None):
    global _LAST_PANE_TEXT
    text = _LAST_PANE_TEXT
    if text is None:
        rc, out, err = run_herdr(
            ["pane", "read", pane, "--source", "recent-unwrapped",
             "--lines", "200"], machine)
        if rc != 0:
            return None, None, "peer screen not readable (dialog may cover it)"
        try:
            text = json.loads(out)["result"]["read"]["text"]
        except Exception:
            text = out
        _LAST_PANE_TEXT = text
    tail = _tail_from_pane_text(text, token, sid, prompt=prompt)
    if tail is None:
        return None, None, "peer screen not readable (dialog may cover it)"
    last_line = tail.splitlines()[-1] if tail.splitlines() else None
    return tail, last_line, None

def _sentinel_scan_tail(pane, token, sid, machine, lines=200):
    """Big-window rescan: return the LAST matching sentinel line for this task."""
    global _LAST_PANE_TEXT
    rc, out, err = run_herdr(
        ["pane", "read", pane, "--source", "recent-unwrapped", "--lines", str(lines)], machine)
    if rc != 0:
        return None, herdr_error_rc(err, 8)
    try:
        txt = json.loads(out)["result"]["read"]["text"]
    except Exception:
        txt = out
    _LAST_PANE_TEXT = txt
    last = None
    for line, joined in _join_wrapped_sentinels(txt.splitlines()):
        m = SENTINEL_RE.match(line)
        if m and _token_matches(m.group(1), token, sid, joined=joined):
            last = line
    return last, None

def _confirm_sentinel(pane, token, sid, machine, no_agent):
    """Hit confirmation: agent must not be working/blocked before AND after
    the 2s stability window (r5#2), and the matched line must still be the
    last HAO_DONE for this task. Returns the line or None."""
    def _st():
        if no_agent:
            return None
        rc, out, _ = run_herdr(["agent", "get", pane], machine)
        if rc != 0:
            return None
        try:
            return json.loads(out)["result"]["agent"].get("agent_status")
        except Exception:
            return None
    if _st() in ("working", "blocked"):
        return None
    time.sleep(2)
    if _st() in ("working", "blocked"):
        return None
    last, _err = _sentinel_scan_tail(pane, token, sid, machine)
    return last

FAST_PATH_SECONDS = 30

WORKING_SCAN_INTERVAL = 10

SETTLED_SCAN_INTERVAL = 2

def _finish_sentinel(l, sid, ml, pane, token, machine, prompt=None):
    rec = _safe_get(l, sid) or {}
    if rec.get("summary"):
        # summary is the higher-priority payload; skip the pane read
        return _finish_done(l, sid, ml, None, None, None)
    tail, last_line, note = _completion_tail(
        pane, token, sid, machine, prompt=prompt)
    return _finish_done(l, sid, ml, tail, note, last_line)

def _finish_done(l, sid, ml, tail=None, tail_note=None, last_line=None):
    had_done = False
    has_summary = False
    try:
        rec = l.get(sid)
        had_done = bool(rec and rec.get("status") == "done")
        has_summary = bool(rec and rec.get("summary"))
    except Exception:
        pass
    try:
        l.write_done(sid, matched_line=ml, wait_consumed=True, create=False)
    except Exception as e:
        _ledger_warn(e)  # r7#1: confirmed completion must still be returned
    out = {"status": "done", "matched_line": ml}
    if (not had_done or not has_summary) and (tail is not None or tail_note is not None):
        out["tail"] = tail
        out["last_line"] = last_line
    if tail_note is not None and (not had_done or not has_summary):
        out["tail_note"] = tail_note
    return out

def _wait_unified(pane, sid, token, timeout, machine, no_agent, accept_unknown,
                  mode):
    """Shared sentinel/lifecycle wait loop.

    mode="sentinel": wait-output fast path, then agent-wait backstop.
    mode="lifecycle": submit_seq activity gate with sentinel evidence.
    Completion always needs task-level evidence (sentinel or ledger done).
    """
    _led = _load_module("hao_ledger", "ledger.py")
    global _LAST_PANE_TEXT, _WAIT_PANE
    _LAST_PANE_TEXT = None
    _WAIT_PANE = pane
    l = _led.Ledger()
    rec0 = _safe_get(l, sid) or {}
    prompt = rec0.get("prompt")
    submit_seq = rec0.get("submit_seq") or 0
    start = time.time()
    deadline = None if timeout == 0 else start + (timeout or 1800)
    observed_working = False
    last_status = None
    seen_record = bool(rec0) if mode == "lifecycle" else False
    sentinel_seen = False
    validated_ml = None
    response_warned = False
    last_pane_scan = start
    saw_activity = False
    while deadline is None or time.time() < deadline:
        rec = _wait_round_rec(l, sid)
        if rec:
            seen_record = True
        elif _wait_consumed(l, sid, seen_record):
            return 3
        token = rec.get("token") or token  # ledger holds the full token
        prompt = rec.get("prompt") or prompt
        kind, payload = _wait_common_check(rec)
        if kind == "done":
            return payload
        if kind == "cancelled":
            return 10
        gate, last_status, agent = _agent_status_gate(
            pane, machine,
            False if mode == "lifecycle" else no_agent,
            True if mode == "lifecycle" else accept_unknown)
        if last_status == "working":
            observed_working = True
        if gate is not None:
            # Herdr-level failure (8) must not trigger another herdr call.
            if gate == 8:
                return gate
            if _deadline_passed(deadline):
                return _wait_timeout(observed_working, last_status, timeout,
                                     seen_record)
            if mode == "sentinel":
                # Only status gates (3/5/9) get the pre-give-up rescan.
                last, _e = _sentinel_scan_tail(pane, token, sid, machine)
                if last:
                    return _finish_sentinel(
                        l, sid, last, pane, token, machine, prompt=prompt)
            if validated_ml is not None:
                return _finish_sentinel(
                    l, sid, validated_ml, pane, token, machine,
                    prompt=prompt)
            if gate == 5 and not sentinel_seen:
                _set_blocked_hint(pane)
            return gate
        if _deadline_passed(deadline):
            return _wait_timeout(observed_working, last_status, timeout,
                                 seen_record)

        if mode == "lifecycle":
            if last_status == "unknown":
                return 6  # lifecycle does not support unknown agents
            seq = agent.get("state_change_seq") or 0
            if seq > submit_seq or last_status == "working":
                saw_activity = True
            if _deadline_passed(deadline):
                return _wait_timeout(observed_working, last_status, timeout,
                                     seen_record)
            # task-level evidence is checked BEFORE the no-activity exit9
            # (r5#3): a late sentinel wins over the activity gate
            ml, errc, _stale = _sentinel_check(pane, token, sid, machine)
            if errc is not None:
                return errc
            if ml:
                sentinel_seen = True
                validated_ml = ml
                if _deadline_passed(deadline):
                    return _wait_timeout(observed_working, last_status,
                                         timeout, seen_record)
                conf = _confirm_sentinel(pane, token, sid, machine, no_agent)
                if conf:
                    return _finish_sentinel(
                        l, sid, conf, pane, token, machine, prompt=prompt)
            if _deadline_passed(deadline):
                return _wait_timeout(observed_working, last_status, timeout,
                                     seen_record)
            last, errc2 = _sentinel_scan_tail(pane, token, sid, machine)
            if errc2 is not None:
                return errc2
            if last:
                sentinel_seen = True
                validated_ml = last
                if _deadline_passed(deadline):
                    return _wait_timeout(observed_working, last_status,
                                         timeout, seen_record)
                conf = _confirm_sentinel(pane, token, sid, machine, no_agent)
                if conf:
                    return _finish_sentinel(
                        l, sid, conf, pane, token, machine, prompt=prompt)
            elif last_status in ("idle", "done"):
                time.sleep(SETTLED_SCAN_INTERVAL)
            response_warned = _maybe_warn_unresponsive(
                pane, time.time() - start, last_status, observed_working,
                sentinel_seen, response_warned)
            if not saw_activity and time.time() - start > 5:
                return 9  # no activity observed for this task
            if _deadline_passed(deadline):
                return _wait_timeout(observed_working, last_status, timeout,
                                     seen_record)
            rw, _, ew = run_herdr(["agent", "wait", pane,
                                   "--until", "idle", "--until", "done",
                                   "--until", "blocked", "--timeout", "8000"],
                                  machine)
            if (rw != 0 and _herdr_err_code(ew) != "timeout"
                    and "timed out" in ew.lower()):
                return herdr_error_rc(ew, 8)
            continue

        if time.time() - start < FAST_PATH_SECONDS:
            if (last_status == "working"
                    and time.time() - last_pane_scan
                    < WORKING_SCAN_INTERVAL):
                # Active TUI output: reading the pane here makes herdr
                # scroll it. Wait on agent state instead; the pane scan
                # below still runs as a low-frequency fallback.
                rw, _, ew = run_herdr(["agent", "wait", pane,
                                       "--until", "idle", "--until", "done",
                                       "--until", "blocked",
                                       "--timeout", "2000"], machine)
                if (rw != 0 and _herdr_err_code(ew) != "timeout"
                        and "timed out" in ew.lower()):
                    return herdr_error_rc(ew, 8)
                if _deadline_passed(deadline):
                    return _wait_timeout(observed_working, last_status,
                                         timeout, seen_record)
            else:
                last_pane_scan = time.time()
                ml, errc, stale = _sentinel_check(pane, token, sid, machine)
                if errc is not None:
                    return errc
                if stale:
                    # wait-output returns the first sentinel on screen, which
                    # may be an older task's. It returned instantly, so pause
                    # for the time a real 1s wait would have taken, then scan
                    # the tail for this task's sentinel in the same round.
                    time.sleep(1)
                    last, serr = _sentinel_scan_tail(pane, token, sid, machine)
                    if serr is not None:
                        return serr
                    ml = last
                if ml:
                    sentinel_seen = True
                    validated_ml = ml
                    if _deadline_passed(deadline):
                        return _wait_timeout(observed_working, last_status,
                                             timeout, seen_record)
                    conf = _confirm_sentinel(pane, token, sid, machine, no_agent)
                    if conf:
                        return _finish_sentinel(
                            l, sid, conf, pane, token, machine,
                            prompt=prompt)
                time.sleep(0.5)
        else:
            if _deadline_passed(deadline):
                return _wait_timeout(observed_working, last_status, timeout,
                                     seen_record)
            if not no_agent:
                rw, _, ew = run_herdr(["agent", "wait", pane,
                                       "--until", "idle", "--until", "done",
                                       "--until", "blocked",
                                       "--timeout", "8000"], machine)
                if (rw != 0 and _herdr_err_code(ew) != "timeout"
                        and "timed out" in ew.lower()):
                    return herdr_error_rc(ew, 8)
            if _deadline_passed(deadline):
                return _wait_timeout(observed_working, last_status, timeout,
                                     seen_record)
            last, errc = _sentinel_scan_tail(pane, token, sid, machine)
            if errc is not None:
                return errc
            if last:
                sentinel_seen = True
                validated_ml = last
                if _deadline_passed(deadline):
                    return _wait_timeout(observed_working, last_status,
                                         timeout, seen_record)
                conf = _confirm_sentinel(pane, token, sid, machine, no_agent)
                if conf:
                    return _finish_sentinel(
                        l, sid, conf, pane, token, machine,
                        prompt=prompt)
            else:
                time.sleep(SETTLED_SCAN_INTERVAL
                           if last_status in ("idle", "done") else 0.5)
        response_warned = _maybe_warn_unresponsive(
            pane, time.time() - start, last_status, observed_working,
            sentinel_seen, response_warned)
    return _wait_timeout(observed_working, last_status, timeout,
                         seen_record)


def _wait_sentinel(pane, sid, token, timeout, machine, no_agent, accept_unknown):
    return _wait_unified(pane, sid, token, timeout, machine, no_agent,
                         accept_unknown, "sentinel")


def _wait_lifecycle(pane, sid, token, timeout, machine, no_agent, accept_unknown):
    return _wait_unified(pane, sid, token, timeout, machine, no_agent,
                         accept_unknown, "lifecycle")


RESPONSE_WARN_S = 15


def _maybe_warn_unresponsive(pane, elapsed, status, observed_working,
                             sentinel_seen, warned):
    if (warned or sentinel_seen or observed_working
            or elapsed < RESPONSE_WARN_S):
        return warned
    if status in ("idle", "done"):
        print(f"hao wait: warning: peer on {pane} has not left idle/done "
              f"after 15s and no ledger/sentinel evidence arrived; it may "
              f"not have received the prompt (e.g. still starting); inspect "
              f"with: herdr pane read {pane}", file=sys.stderr)
        return True
    return warned


def _wait_file(pane, sid, token, timeout, machine):
    """File mode: completion = stable non-empty regular result file, or
    ledger done. Re-reads the ledger every round (result_path may arrive
    late). Tolerates panes without an agent."""
    _led = _load_module("hao_ledger", "ledger.py")
    l = _led.Ledger()
    deadline = None if timeout == 0 else time.time() + (timeout or 1800)
    last_size = None
    seen_record = False
    while deadline is None or time.time() < deadline:
        rec = _wait_round_rec(l, sid)
        if rec:
            seen_record = True
        elif _wait_consumed(l, sid, seen_record):
            return 3
        kind, payload = _wait_common_check(rec)
        if kind == "done":
            return payload
        if kind == "cancelled":
            return 10
        if _deadline_passed(deadline):
            return 4
        rc, out, err = run_herdr(["agent", "get", pane], machine)
        if rc != 0:
            if _herdr_err_code(err) == "agent_not_found":
                # herdr returns agent_not_found for missing panes too:
                # confirm the pane itself still exists before skipping the gate
                if _deadline_passed(deadline):
                    return 4
                rcp, _, errp = run_herdr(["pane", "get", pane], machine)
                if rcp != 0:
                    return herdr_error_rc(errp, 8)
            else:
                return herdr_error_rc(err, 8)
        else:
            try:
                st = json.loads(out)["result"]["agent"].get("agent_status")
            except Exception:
                st = None
            if st == "blocked":
                if _deadline_passed(deadline):
                    return 4
                _set_blocked_hint(pane)
                return 5
            if st in ("exited", "closed"):
                return 4 if _deadline_passed(deadline) else 3
        rec = _safe_get(l, sid) or {}
        rp = rec.get("result_path")
        if not rp:
            # r9#2 fallback: ask's convention path (state_dir/<sid>/result.md)
            # survives even when the ledger write was lost
            rp = os.path.join(_led.state_dir(), sid, "result.md")
        if rp and os.path.isfile(rp):
            sz = os.path.getsize(rp)
            if sz > 0 and sz == last_size:
                content = safe_read(sid, rp)
                try:
                    l.write_done(sid, result_path=rp, wait_consumed=True,
                                 create=False)
                except Exception as e:
                    _ledger_warn(e)  # r7#1: stable file is the evidence
                out = {"status": "done", "result_path": rp}
                if content is not None:
                    out["tail"] = content
                    out["result_consumed"] = True
                    try:
                        l.consume(sid)
                    except Exception as e:
                        _ledger_warn(e)
                else:
                    out["tail_note"] = ("result file unreadable; "
                                        "left in place for hao result")
                return out
            last_size = sz
        time.sleep(1)
    return 4

def _reply_payload(result, sid):
    """Payload priority: ledger summary, then result.md, then tail.

    A result file is read into `tail` and marked consumed; the caller then
    removes the record and the result tree. Returns whether the caller
    should consume the ledger record."""
    if result.get("summary"):
        return True
    rp = result.get("result_path")
    if not rp:
        led = _load_module("hao_ledger", "ledger.py")
        rp = os.path.join(led.state_dir(), sid, "result.md")
    if rp and os.path.isfile(rp):
        content = safe_read(sid, rp)
        if content is not None:
            result["tail"] = content
            result["result_path"] = rp
            result["result_consumed"] = True
            return True
        result["tail_note"] = ("result file unreadable; "
                               "left in place for hao result")
        return False
    return not result.get("result_path")


def cmd_wait(target, token, timeout, mode="sentinel", machine=None,
             no_agent=False, accept_unknown=False):
    pane, resolve_rc = _resolve_target_ex(target, machine)
    if resolve_rc:
        return resolve_rc
    try:
        sid = normalize_id(token)
    except ValueError:
        _set_error("invalid token; expected 12-hex shortid or hao- token")
        return 2
    global _WAIT_DIAG
    _WAIT_DIAG = None
    if mode == "file":
        result = _wait_file(pane, sid, token, timeout, machine)
    elif mode == "lifecycle":
        result = _wait_lifecycle(pane, sid, token, timeout, machine, no_agent, accept_unknown)
    else:
        result = _wait_sentinel(pane, sid, token, timeout, machine, no_agent, accept_unknown)
    if isinstance(result, dict) and result.get("status") == "done":
        try:
            _led = _load_module("hao_ledger", "ledger.py")
            l = _led.Ledger()
        except Exception as e:
            l = None
            _ledger_warn(e)
        if l is not None:
            try:
                l.write_done(sid, wait_consumed=True, create=False)
            except Exception as e:
                _ledger_warn(e)
        consume_now = False
        if isinstance(result, dict):
            consume_now = _reply_payload(result, sid)
        if l is not None and consume_now:
            try:
                l.consume(sid)
            except Exception as e:
                _ledger_warn(e)
    elif result == 10:
        try:
            _led = _load_module("hao_ledger", "ledger.py")
            _led.Ledger().consume(sid)
        except Exception as e:
            _ledger_warn(e)
    if result == 4 and timeout:
        _set_error(_WAIT_DIAG or f"timeout after {timeout}s")
    return result

def cmd_done(token, summary, final=False):
    _led = _load_module("hao_ledger", "ledger.py")
    try:
        sid = normalize_id(token)
    except ValueError:
        _set_error("invalid token; expected 12-hex shortid or hao- token")
        return 2
    try:
        l = _led.Ledger()
        rec = l.get(sid)
        ledger_readable = True
    except Exception as e:
        l = None
        rec = None
        ledger_readable = False
        _ledger_warn(e)
    if rec is None and ledger_readable:
        return fail(3, f"task {sid} not found")
    if rec and rec.get("status") == "cancelled":
        return fail(6, f"task {sid} was cancelled; refusing to mark done")
    if final and (not rec or rec.get("status") != "done"):
        target = rec.get("target") if rec else None
        mach = rec.get("machine") if rec else None
        if target:
            st = current_state(target, mach)
            if st not in ("idle", "done"):
                return fail(5, f"agent {target} is {st}; --final requires idle or done")
    try:
        if l is not None:
            l.write_done(sid, summary=summary, create=False)
    except Exception as e:
        # r8#3: the sentinel printed below is the fallback evidence —
        # a ledger failure must never swallow it
        _ledger_warn(e)
    # same-machine wake: fixed template, no peer summary injection;
    # wake caller missing -> exit3 (ledger done + sentinel still stand)
    wake = rec.get("wake") if rec else None
    wake_rc = 0
    if wake:
        target = rec.get("target") if rec else None
        wake_msg = f"[HAO_WAKE] {sid} done"
        if target:
            wake_msg += f" — run: {hao_command()} wait {target} --token {sid}"
        rw, _, ew = run_herdr(["agent", "prompt", wake, wake_msg])
        if rw != 0:
            wake_rc = herdr_error_rc(ew, 8)
    if summary:
        print(summary, flush=True)
    print(f"HAO_DONE {rec.get('token', token) if rec else token}", flush=True)
    if _JSON_OUTPUT:
        payload = {"ok": wake_rc == 0, "token": rec.get("token", token) if rec else token,
                   "exit": wake_rc}
        if wake_rc:
            payload["error"] = "wake failed"
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        global _JSON_HANDLED
        _JSON_HANDLED = True
    return wake_rc
