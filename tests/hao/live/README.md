# hao live scenario suite

Optional, **real-machine** checks for the hao skill. The unit suite uses stubs;
this suite exercises a real herdr workspace and a throwaway agent.

It is not discovered by `unittest discover` (no `__init__.py`, filename does
not start with `test_`).

## Prerequisites

- herdr running, with `HERDR_ENV=1` and `HERDR_WORKSPACE_ID` set.
- A `pi` agent on PATH (`herdr agent start --kind pi`). Scenarios that need
  `claude` are skipped unless `--kinds` includes it and `claude` is on PATH.
- Run from anywhere, but the suite creates its own tab in the given workspace
  (`--label hao-live --cwd /tmp --no-focus`) and closes it in `finally`.
- The suite uses its own temporary `HAO_STATE_DIR`; it never reads or writes
  `~/.local/state/hao`.

## Commands

```bash
python3 tests/hao/live/run_live.py --list
HERDR_ENV=1 HERDR_WORKSPACE_ID=w2 python3 tests/hao/live/run_live.py --quick
HERDR_ENV=1 HERDR_WORKSPACE_ID=w2 python3 tests/hao/live/run_live.py
HERDR_ENV=1 HERDR_WORKSPACE_ID=w2 python3 tests/hao/live/run_live.py \
    --filter lifecycle --kinds pi,claude
```

- `--list` works without herdr and prints all 44 scenarios.
- `--quick` skips the three slow scenarios (long task, six dispatches,
  pane-read frequency).
- `--filter SUBSTR` runs scenarios whose name contains `SUBSTR`.
- `--kinds pi,claude` selects agent kinds for end-to-end scenarios (default
  `pi`).
- Exit code 0 when nothing failed, 1 on any FAIL. A missing prerequisite
  (agent kind not available) is reported as SKIP.

## What it checks

Naming and roles, tiered briefs, wait/ledger completion, `--text-only`,
lifecycle dispatch, the pane-read frequency regression, file-mode inline
results and zero residue, cancel/abort/stop, restore/clear, doctor/read-only
commands, an unsent input draft, and an optional Claude Code peer.

Each scenario is independent and calls `ctx.settle()` between dispatches.
Answers are accepted from `summary`, `tail` or `last_line` because a peer may
or may not call `hao done`.

## Safety

The suite only creates and closes its own tab(s). It never sends keys to other
panes, never uses `pkill -f`/`killall`, and cleans `HAO_STATE_DIR` in
`finally` (the last scenario asserts the state directory is gone).
