"""Per-shortid locked task ledger for herdr-agent-ops coordination.

Best-effort coordination cache. Names are zero-registry (pane labels);
this ledger only tracks in-flight task state for wait/cancel/wake/result.
All writes are fresh read-modify-write field merges under a per-shortid lock.
The state directory is resolved per call (env changes take effect immediately).
"""
import fcntl
import json
import os
import re
import shutil
import time

SHORTID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def state_dir():
    base = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return os.path.join(base, "hao", "tasks")


def _path(shortid):
    if not SHORTID_RE.match(shortid or ""):
        raise ValueError(f"invalid shortid: {shortid!r}")
    return os.path.join(state_dir(), shortid + ".json")


class Ledger:
    def __init__(self):
        # lazy on purpose: constructing a Ledger must not fail on a
        # read-only/missing state dir — waits degrade gracefully and
        # _rw creates the directory on demand
        pass

    def _rw(self, shortid, fn, lock_timeout=5.0, create=True):
        p = _path(shortid)
        os.makedirs(os.path.dirname(p), mode=0o700, exist_ok=True)
        with open(p + ".lock", "w") as lf:
            deadline = time.time() + lock_timeout
            while True:
                try:
                    fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.time() >= deadline:
                        raise TimeoutError(f"ledger lock timeout: {shortid}")
                    time.sleep(0.05)
            rec = {}
            exists = os.path.exists(p)
            if exists:
                with open(p) as f:
                    rec = json.load(f)
            if not exists and not create:
                fcntl.flock(lf, fcntl.LOCK_UN)
                return None
            fn(rec)
            tmp = p + ".tmp"
            with open(tmp, "w") as f:
                os.chmod(tmp, 0o600)
                json.dump(rec, f)
            os.replace(tmp, p)
            fcntl.flock(lf, fcntl.LOCK_UN)
        return rec

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
        # field-level merge of updated only; never creates a stub record.
        if not os.path.exists(_path(shortid)):
            return None
        return self._rw(shortid,
                        lambda rec: rec.__setitem__("updated", time.time()),
                        create=False)

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

    def cleanup(self, ttl_s=86400, dry_run=False, all_=False):
        stats = {"removed": 0, "locks_removed": 0,
                 "dirs_removed": 0, "kept_running": 0}
        removed_ids = set()
        now = time.time()
        base = state_dir()
        if not os.path.isdir(base):
            return stats
        lock_path = os.path.join(base, ".cleanup.lock")
        with open(lock_path, "w") as lf:
            try:
                fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return stats  # another cleanup holds the lock: conservatively skip
            for fn in os.listdir(base):
                if not fn.endswith(".json"):
                    continue
                path = os.path.join(base, fn)
                try:
                    with open(path) as f:
                        rec = json.load(f)
                except Exception:
                    continue  # skip bad JSON
                status = rec.get("status")
                aged = now - rec.get("updated", 0) > ttl_s
                if status == "running":
                    remove = aged and not all_
                    if not remove:
                        stats["kept_running"] += 1
                elif status in ("done", "cancelled"):
                    remove = all_ or aged
                else:
                    remove = aged
                if remove:
                    sid = fn[:-5]
                    if dry_run:
                        stats["removed"] += 1
                        removed_ids.add(sid)
                    else:
                        try:
                            os.remove(path)
                            stats["removed"] += 1
                            removed_ids.add(sid)
                        except OSError:
                            pass
            # orphan locks and result directories
            for fn in os.listdir(base):
                path = os.path.join(base, fn)
                if fn.endswith(".json.lock"):
                    sid = fn[:-len(".json.lock")]
                    if (sid in removed_ids
                            or not os.path.exists(os.path.join(base, sid + ".json"))):
                        stats["locks_removed"] += 1
                        if not dry_run:
                            try:
                                os.remove(path)
                            except OSError:
                                stats["locks_removed"] -= 1
                elif os.path.isdir(path) and not os.path.islink(path) and not fn.startswith("."):
                    if (fn in removed_ids
                            or not os.path.exists(os.path.join(base, fn + ".json"))):
                        stats["dirs_removed"] += 1
                        if not dry_run:
                            try:
                                shutil.rmtree(path)
                            except OSError:
                                stats["dirs_removed"] -= 1
            fcntl.flock(lf, fcntl.LOCK_UN)
        return stats
