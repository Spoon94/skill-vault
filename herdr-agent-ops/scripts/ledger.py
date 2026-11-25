"""Per-shortid locked task ledger for herdr-agent-ops coordination.

Best-effort coordination cache. Names are zero-registry (pane labels);
this ledger only tracks in-flight task state for wait/cancel/wake/result.
All writes are fresh read-modify-write field merges under a per-shortid lock.

The ledger is runtime-only: it lives in a system temporary directory, only
exists while tasks do, and is removed as soon as a waiter/result consumes it.
The state directory is resolved per call (env changes take effect immediately).
"""
import fcntl
import json
import os
import re
import shutil
import sys
import tempfile
import time

SHORTID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def state_dir():
    override = os.environ.get("HAO_STATE_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    if sys.platform.startswith("linux") and os.environ.get("XDG_RUNTIME_DIR"):
        return os.path.join(os.environ["XDG_RUNTIME_DIR"], "hao", "tasks")
    uid = getattr(os, "getuid", lambda: "user")()
    return os.path.join(tempfile.gettempdir(), f"hao-{uid}", "tasks")


def _path(shortid):
    if not SHORTID_RE.match(shortid or ""):
        raise ValueError(f"invalid shortid: {shortid!r}")
    return os.path.join(state_dir(), shortid + ".json")


def _ensure_dir():
    base = state_dir()
    parent = os.path.dirname(base)
    parent_existed = os.path.isdir(parent)
    os.makedirs(base, mode=0o700, exist_ok=True)
    parents = [parent] if (not parent_existed
                           or os.path.basename(parent).startswith("hao")) else []
    for path in [base] + parents:
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
    return base


def _remove(path):
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def _cancelled_ts(rec):
    vals = [v for v in (rec.get("cancelled_at"), rec.get("updated")) if v]
    return min(vals) if vals else 0


def _remove_tree(path):
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
            return True
    except OSError:
        pass
    return False


class Ledger:
    def __init__(self):
        # Lazy on purpose: constructing a Ledger must not create anything.
        pass

    def _rw(self, shortid, fn, lock_timeout=5.0, create=True):
        p = _path(shortid)
        if not create and not os.path.exists(p):
            return None
        if create:
            base = _ensure_dir()
        else:
            base = os.path.dirname(p)
            if not os.path.isdir(base):
                return None
        with open(p + ".lock", "a+") as lf:
            try:
                os.chmod(lf.name, 0o600)
            except OSError:
                pass
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
            if not exists and not create:
                fcntl.flock(lf, fcntl.LOCK_UN)
                return None
            if exists:
                with open(p) as f:
                    rec = json.load(f)
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
        return self._rw(shortid, go)

    def write_done(self, shortid, create=True, **fields):
        def go(rec):
            rec.update(fields)
            rec["status"] = "done"
            rec["updated"] = time.time()
        return self._rw(shortid, go, create=create)

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
                rec["cancelled_at"] = time.time()
                rec["updated"] = time.time()
                rc = 0
        if self._rw(shortid, go, create=False) is None:
            return 3
        return rc

    def mark_interrupted(self, shortid):
        """Mark a cancelled record as interrupted; waiters/tidy consume it."""
        def go(rec):
            rec["interrupted"] = True
            rec["interrupted_at"] = time.time()
            rec["updated"] = time.time()
        return self._rw(shortid, go, create=False)

    def consume(self, shortid, keep_result=False):
        """Delete a consumed record and its per-record artifacts.

        Call after wait observes done/cancelled, or after result reads a file.
        keep_result=True leaves a file-mode record/result for `hao result`.
        """
        if keep_result:
            return False
        p = _path(shortid)
        base = os.path.dirname(p)
        lock_path = p + ".lock"
        removed = False
        if os.path.exists(lock_path) and os.path.exists(p):
            try:
                with open(lock_path, "a+") as lf:
                    deadline = time.time() + 5.0
                    while True:
                        try:
                            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except OSError:
                            if time.time() >= deadline:
                                break  # best-effort: never wedge a wait return
                            time.sleep(0.05)
                    removed = _remove(p)
                    _remove(lock_path)
                    fcntl.flock(lf, fcntl.LOCK_UN)
            except OSError:
                removed = _remove(p)
                _remove(lock_path)
        elif os.path.exists(p):
            removed = _remove(p)
            _remove(lock_path)
        _remove_tree(os.path.join(base, shortid))
        self._tidy()
        return removed

    def tidy(self):
        self._tidy()

    def tidy_cancelled(self, is_running, max_age=3600, force=False):
        """Remove cancelled tombstones whose target is no longer running
        or whose cancellation is older than max_age. Callers must invoke
        this only from state-changing commands, doctor, or clean."""
        removed = 0
        base = state_dir()
        if not os.path.isdir(base):
            return removed
        try:
            names = os.listdir(base)
        except OSError:
            return removed
        now = time.time()
        for fn in names:
            if not fn.endswith(".json"):
                continue
            sid = fn[:-5]
            try:
                with open(os.path.join(base, fn)) as f:
                    rec = json.load(f)
            except Exception:
                continue
            if rec.get("status") != "cancelled":
                continue
            if rec.get("interrupted"):
                interrupted_at = rec.get("interrupted_at",
                                         rec.get("updated", 0))
                heartbeat_age = now - rec.get("updated", 0)
                if not force and (now - interrupted_at <= 60
                                  or heartbeat_age <= 60):
                    continue
                if self.consume(sid):
                    removed += 1
                continue
            cancelled_at = _cancelled_ts(rec)
            try:
                running = bool(is_running(rec))
            except Exception:
                running = True  # unreadable peer state: retain for a retry
            if force or now - cancelled_at > max_age or not running:
                if self.consume(sid):
                    removed += 1
        return removed

    def _tidy(self):
        """Collect orphan locks/results and remove the empty state tree."""
        base = state_dir()
        if not os.path.isdir(base):
            return
        try:
            names = os.listdir(base)
        except OSError:
            return
        for fn in names:
            path = os.path.join(base, fn)
            if fn.endswith(".json.lock"):
                sid = fn[:-len(".json.lock")]
                if not os.path.exists(os.path.join(base, sid + ".json")):
                    _remove(path)
            elif (os.path.isdir(path) and not os.path.islink(path)
                  and not fn.startswith(".")):
                if not os.path.exists(os.path.join(base, fn + ".json")):
                    _remove_tree(path)
        # legacy cleanup lock no longer used
        try:
            names = os.listdir(base)
        except OSError:
            return
        if any(fn.endswith(".json") for fn in names):
            return
        _remove(os.path.join(base, ".cleanup.lock"))
        try:
            os.rmdir(base)
        except OSError:
            return
        parent = os.path.dirname(base)
        while os.path.basename(parent).startswith("hao"):
            try:
                os.rmdir(parent)
            except OSError:
                break
            parent = os.path.dirname(parent)

    def cleanup(self, ttl_s=86400, dry_run=False, all_=False, is_running=None):
        stats = {"removed": 0, "locks_removed": 0,
                 "dirs_removed": 0, "kept_running": 0}
        removed_ids = set()
        now = time.time()
        base = state_dir()
        if not os.path.isdir(base):
            return stats
        try:
            dfd = os.open(base, os.O_RDONLY)
        except OSError:
            return stats
        try:
            try:
                fcntl.flock(dfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
                    active = None
                    if is_running is not None and (aged or all_):
                        try:
                            active = bool(is_running(rec))
                        except Exception:
                            active = True  # unreadable peer state: conservative
                    if all_:
                        # --all may remove running records only when the
                        # target is confirmed inactive/gone; active or
                        # unreadable targets stay.
                        remove = active is False
                    else:
                        remove = aged and active is not True
                    if not remove:
                        stats["kept_running"] += 1
                elif status in ("done", "cancelled"):
                    remove = all_ or aged
                    if status == "cancelled":
                        if rec.get("interrupted") and not all_:
                            interrupted_at = rec.get("interrupted_at",
                                                     rec.get("updated", 0))
                            heartbeat_age = now - rec.get("updated", 0)
                            remove = (now - interrupted_at > 60
                                      and heartbeat_age > 60)
                        else:
                            cancelled_at = _cancelled_ts(rec)
                            remove = remove or (now - cancelled_at > 3600)
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
                        if not dry_run and not _remove(path):
                            stats["locks_removed"] -= 1
                elif os.path.isdir(path) and not os.path.islink(path) and not fn.startswith("."):
                    if (fn in removed_ids
                            or not os.path.exists(os.path.join(base, fn + ".json"))):
                        stats["dirs_removed"] += 1
                        if not dry_run and not _remove_tree(path):
                            stats["dirs_removed"] -= 1
            fcntl.flock(dfd, fcntl.LOCK_UN)
        finally:
            os.close(dfd)
        if not dry_run:
            self._tidy()
        return stats
