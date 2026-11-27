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
  pane-read frequency): about 5 minutes; the full run takes about 8 minutes.
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

Each scenario calls `ctx.settle()` between dispatches. Answers are accepted
from `summary`, `tail` or `last_line` because a peer may or may not call
`hao done`.

## Writing a scenario: what the real machine taught

- **Scenarios that leave unfinished work must be isolated.** A cancelled or
  interrupted long task keeps running on the peer (pi resumes the queued
  prompts after an interrupt), and later scenarios would inherit a busy,
  confused peer. Mark them `@scenario(..., isolate=True)`: they get their own
  throwaway instance, which is destroyed afterwards.
- **Every instance the suite starts gets a unique herdr agent name** (derived
  from the suite's pid and a counter). A fixed name made a second instance
  fail with `agent_name_taken` whenever the shared peer had not been renamed
  yet; with the pid in the name, an instance left behind by a crashed run is
  reported instead of silently collided with.
- **The peer's pane is not a reliable witness.** pi hard-wraps a pasted prompt
  with a right border, and sometimes clears the screen entirely. To assert
  what was sent, read the task's ledger record (`HAO_STATE_DIR/<sid>.json`
  has the `prompt`) while the task is still running.
- **`ask --wait` returns while the peer still shows its "Working" banner.**
  Call `ctx.settle()` before reading the input box or the pane.
- **Dispatching is not the peer starting.** Wait for `working` before
  asserting anything about a running peer (`cancel`, `stop`, …).
- **A draft in the input box is glued in front of the task**, so its wording
  reaches the model. Use a neutral half-typed line; a label such as
  "UNSENT DRAFT" can make a weak model refuse the task as "not sent".
- Model latency varies (a routed model once took 109s to its first token):
  judge the wait by its result, not by a tight timing bound.
- **A fresh Claude Code instance is slow on its first turn** (43–69s to its
  first token, spent on start-up and on reading the hao script before it
  trusts `hao done`). Warm it up with `hao say` and wait for it to settle
  before dispatching the measured task; give that task a generous timeout.

## Safety

The suite only creates and closes its own tab(s) — the shared peer's tab and
one per isolated scenario. It never sends keys to other
panes, never uses `pkill -f`/`killall`, and cleans `HAO_STATE_DIR` in
`finally` (the last scenario asserts the state directory is gone).
