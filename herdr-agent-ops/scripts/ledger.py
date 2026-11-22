"""Per-shortid locked task ledger for herdr-agent-ops coordination.

Best-effort coordination cache. Names are zero-registry (pane labels);
this ledger only tracks in-flight task state for wait/cancel/wake/result.
All writes are fresh read-modify-write field merges under a per-shortid lock.
"""
import fcntl
import json
import os
import re
import time

STATE = os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
    "hao", "tasks",
)
SHORTID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def _path(shortid):
    if not SHORTID_RE.match(shortid or ""):
        raise ValueError(f"invalid shortid: {shortid!r}")
    return os.path.join(STATE, shortid + ".json")


class Ledger:
    def __init__(self):
        os.makedirs(STATE, mode=0o700, exist_ok=True)

    def _rw(self, shortid, fn):
        p = _path(shortid)
        with open(p + ".lock", "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            rec = {}
            if os.path.exists(p):
                with open(p) as f:
                    rec = json.load(f)
            fn(rec)
            tmp = p + ".tmp"
            with open(tmp, "w") as f:
                os.chmod(tmp, 0o600)
                json.dump(rec, f)
            os.replace(tmp, p)
            fcntl.flock(lf, fcntl.LOCK_UN)

    def write_running(self, shortid, **fields):
        def go(rec):
            if rec.get("status") == "done":
                return  # never downgrade done -> running
            rec.update(fields)
            rec["status"] = "running"
            rec.setdefault("created", time.time())
            rec["updated"] = time.time()
        self._rw(shortid, go)

    def write_done(self, shortid, **fields):
        def go(rec):
            rec.update(fields)
            rec["status"] = "done"
            rec["updated"] = time.time()
        self._rw(shortid, go)

    def heartbeat(self, shortid):
        # field-level merge of updated only (active-waiter heartbeat)
        self._rw(shortid, lambda rec: rec.__setitem__("updated", time.time()))

    def get(self, shortid):
        p = _path(shortid)
        if not os.path.exists(p):
            return None
        with open(p) as f:
            return json.load(f)

    def cancel(self, shortid):
        if not os.path.exists(_path(shortid)):
            return 3
        rc = 0
        def go(rec):
            nonlocal rc
            if rec.get("status") == "done":
                rc = 6  # done > cancelled, no-op
            else:
                rec["status"] = "cancelled"
                rec["updated"] = time.time()
                rc = 0
        self._rw(shortid, go)
        return rc

    def cleanup(self, ttl_s=86400):
        now = time.time()
        lock_path = os.path.join(STATE, ".cleanup.lock")
        with open(lock_path, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            for fn in os.listdir(STATE):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(STATE, fn)) as f:
                        rec = json.load(f)
                except Exception:
                    continue  # skip bad JSON
                # clean terminal/stale and orphan running (no fresh heartbeat)
                if now - rec.get("updated", 0) > ttl_s:
                    os.remove(os.path.join(STATE, fn))
            fcntl.flock(lf, fcntl.LOCK_UN)
