#!/usr/bin/env python3
"""Statement coverage for the hao scripts. Standard library only.

    python3 tests/hao/tools/coverage.py [--top N] [--fail-under PCT] [--json FILE]

Why not `trace` or coverage.py: the suite runs the CLI in subprocesses with
custom environments, so an in-process tracer misses most of the execution, and
the tests load the scripts through paths containing `..`. This tool installs a
start-up hook (sitecustomize + sys.settrace) in a temporary directory, injects
it into every Python subprocess the tests spawn, normalises file names with
realpath, and counts AST statement lines as the denominator.
"""
import ast
import contextlib
import glob
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))          # tests/hao/tools
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))  # tools -> hao -> tests -> repo
TESTS = os.path.join(ROOT, "tests", "hao")
TARGETS = ["hao/scripts/hao", "hao/scripts/waiting.py",
           "hao/scripts/ledger.py", "hao/scripts/names.py"]

HOOK = '''import atexit, json, os, sys
_OUT = os.environ.get("HAO_COV_DIR")
_TARGETS = frozenset(os.path.realpath(p) for p in
                     os.environ.get("HAO_COV_TARGETS", "").split(os.pathsep) if p)
_seen, _real = set(), {}
def _local(frame, event, arg):
    if event == "line":
        _seen.add((frame.f_code.co_filename, frame.f_lineno))
    return _local
def _global(frame, event, arg):
    if event == "call":
        fn = frame.f_code.co_filename
        rp = _real.get(fn)
        if rp is None:
            try:
                rp = os.path.realpath(fn)
            except OSError:
                rp = ""
            _real[fn] = rp
        if rp in _TARGETS:
            return _local
    return None
def _dump():
    try:
        os.makedirs(_OUT, exist_ok=True)
        with open(os.path.join(_OUT, "%d.json" % os.getpid()), "w") as f:
            json.dump(sorted(_seen), f)
    except Exception:
        pass
if _OUT and _TARGETS:
    sys.settrace(_global)
    atexit.register(_dump)
'''


def statements(src):
    return node_lines(ast.parse(src))


def node_lines(node):
    """Absolute line numbers of every executable statement in a node.

    Docstrings are excluded: a docstring is a statement in the AST but the
    compiler turns it into a constant, so it never produces a line event and
    would be reported as uncovered forever. (A re-parsed source segment would
    renumber lines from 1, so always walk the node itself.)"""
    docstrings = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = n.body[0] if n.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                docstrings.add(first.lineno)
    return {n.lineno for n in ast.walk(node)
            if isinstance(n, ast.stmt) and getattr(n, "lineno", None)} - docstrings


def run_suite(hook_dir, out_dir):
    """Run the unit suite with the hook active here and in every subprocess."""
    env = dict(os.environ)
    env["PYTHONPATH"] = hook_dir + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["HAO_COV_DIR"] = out_dir
    env["HAO_COV_TARGETS"] = os.pathsep.join(os.path.join(ROOT, t) for t in TARGETS)
    os.environ.update({k: env[k] for k in ("HAO_COV_DIR", "HAO_COV_TARGETS")})
    code = (
        "import os, subprocess, sys, unittest\n"
        "HOOK = %r\n"
        "_orig = subprocess.Popen.__init__\n"
        "def _init(self, args, *a, **kw):\n"
        "    argv = [args] if isinstance(args, str) else list(args)\n"
        "    if argv and 'python' in os.path.basename(str(argv[0])):\n"
        "        env = dict(os.environ) if kw.get('env') is None else dict(kw['env'])\n"
        "        env['PYTHONPATH'] = HOOK + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')\n"
        "        for k in ('HAO_COV_DIR', 'HAO_COV_TARGETS'):\n"
        "            env[k] = os.environ[k]\n"
        "        kw['env'] = env\n"
        "    return _orig(self, args, *a, **kw)\n"
        "subprocess.Popen.__init__ = _init\n"
        "os.chdir(%r)\n"
        "suite = unittest.defaultTestLoader.discover('.', pattern='test_*.py')\n"
        "res = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w')).run(suite)\n"
        "sys.exit(0 if res.wasSuccessful() else 1)\n" % (hook_dir, TESTS)
    )
    script = os.path.join(hook_dir, "_runner.py")
    with open(script, "w") as f:
        f.write(code)
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        r = subprocess.run([sys.executable, "-B", script], env=env, cwd=TESTS, timeout=900,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:])
        sys.exit("the unit suite failed under the coverage run; fix that first")


def report(out_dir, top):
    real = {os.path.realpath(os.path.join(ROOT, t)): os.path.join(ROOT, t) for t in TARGETS}
    recorded, procs = set(), 0
    for f in glob.glob(os.path.join(out_dir, "*.json")):
        procs += 1
        for fn, ln in json.load(open(f)):
            rp = os.path.realpath(fn)
            if rp in real:
                recorded.add((real[rp], ln))
    per_file, funcs, total_s, total_c = {}, [], 0, 0
    for t in TARGETS:
        path = os.path.join(ROOT, t)
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        st_all, cov = statements(src), {ln for (fn, ln) in recorded if fn == path}
        hit = st_all & cov
        total_s += len(st_all)
        total_c += len(hit)
        per_file[t] = {"covered": len(hit), "statements": len(st_all),
                       "percent": round(100.0 * len(hit) / len(st_all), 1)}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                st = node_lines(node)
                if st:
                    funcs.append({"file": os.path.basename(t), "name": node.name,
                                  "covered": len(st & cov), "statements": len(st)})
    overall = round(100.0 * total_c / total_s, 1) if total_s else 100.0
    return per_file, funcs, overall, procs


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    top, under, out_json = 15, None, None
    i = 0
    while i < len(argv):
        if argv[i] == "--top":
            top = int(argv[i + 1]); i += 2
        elif argv[i] == "--fail-under":
            under = float(argv[i + 1]); i += 2
        elif argv[i] == "--json":
            out_json = argv[i + 1]; i += 2
        else:
            sys.exit(__doc__)
    with tempfile.TemporaryDirectory() as tmp:
        hook_dir, out_dir = os.path.join(tmp, "hook"), os.path.join(tmp, "out")
        os.makedirs(hook_dir)
        os.makedirs(out_dir)
        with open(os.path.join(hook_dir, "sitecustomize.py"), "w") as f:
            f.write(HOOK)
        run_suite(hook_dir, out_dir)
        per_file, funcs, overall, procs = report(out_dir, top)
    print("statement coverage (unit suite, %d traced processes)" % procs)
    for t in TARGETS:
        d = per_file[t]
        print("  %-12s %5d / %5d  %5.1f%%" % (os.path.basename(t), d["covered"], d["statements"], d["percent"]))
    print("  %-12s %5s   overall %5.1f%%" % ("TOTAL", "", overall))
    print("\nfunctions with the most uncovered statements:")
    for f in sorted((f for f in funcs if f["covered"] < f["statements"]),
                    key=lambda f: f["statements"] - f["covered"], reverse=True)[:top]:
        print("  %-26s %-12s %4d / %4d" % (f["name"], f["file"], f["covered"], f["statements"]))
    if out_json:
        with open(out_json, "w") as f:
            json.dump({"overall": overall, "files": per_file, "functions": funcs}, f, indent=1)
    if under is not None and overall < under:
        sys.exit("coverage %.1f%% is below the required %.1f%%" % (overall, under))


if __name__ == "__main__":
    main()
