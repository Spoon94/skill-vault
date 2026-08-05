---
name: agentsview-cli
description: Use when running or scripting the agentsview CLI from the command line — querying, searching, syncing, exporting, or reporting on local AI agent session history. Triggers for cost/usage reports, session search and resume, archive sync, prune/import/export, secret scans, pg/duckdb mirroring, the MCP server, or any `agentsview <command>` invocation, even when the user never says "agentsview" and just asks "what did I spend on Claude this week" or "find where I fixed that timeout". Do NOT use for developing the agentsview codebase itself (parsers, storage, frontend, server internals) — this skill covers CLI usage only.
---

# AgentsView CLI

AgentsView syncs sessions from local AI coding agents (Claude Code, Codex,
Cursor, Copilot, Gemini, and many more) into a local SQLite archive and
exposes them through the `agentsview` binary plus a web UI. Everything is
local; there are no accounts.

This skill covers the CLI surface only — how to run and script `agentsview`
commands against the installed binary. It is not a guide to developing
agentsview itself; for parser/storage/frontend work, follow the repo's
`AGENTS.md` task routes instead. Full upstream docs live in this repo under
`docs/` (rendered at agentsview.io); the condensed references in
`references/` are enough for most CLI tasks.

## Before You Run Anything

1. **Check the installed version.** Features land release by release, so a
   binary installed via brew or the install script may be older than the docs
   describe. Run `agentsview version` first; if a command you need is missing
   from `agentsview help`, confirm it exists in the installed version before
   assuming the docs are wrong. In this repository the bleeding-edge CLI is
   also available via `go run ./cmd/agentsview <command>`.
2. **Data is only as fresh as the last sync.** The archive is populated by
   sync. If results look missing or stale, run `agentsview sync` before
   concluding data does not exist. Freshness-sensitive commands (`usage`,
   `token-use`/`session usage`) sync on demand by default.
3. **Default to read-only operations.** Commands that delete or rebuild data
   (`prune`, `pg push --full`, `embeddings retire`, `recall` imports) deserve
   a preview or explicit confirmation first.

## Command Router

| Want to... | Command | Details |
| --- | --- | --- |
| Browse/list sessions | `session list` | references/sessions.md |
| Resume recent work | `session list --resume` | references/sessions.md |
| Read a session's messages | `session messages <id>` | references/sessions.md |
| Search what was said/done | `session search` | references/sessions.md |
| Session metadata/signals | `session get <id>`, `health [id]` | references/sessions.md |
| Tool calls in a session | `session tool-calls <id>` | references/sessions.md |
| Per-session tokens/cost | `session usage <id>` | references/usage.md |
| Daily cost report | `usage daily` | references/usage.md |
| One-line today spend | `usage statusline` | references/usage.md |
| Active time/concurrency | `activity report` | references/usage.md |
| Workspace analytics | `stats` | references/usage.md |
| Refresh the archive | `agentsview sync` | references/commands.md |
| Serve web UI | `agentsview serve` / `daemon start` | references/commands.md |
| List projects | `agentsview projects` | references/commands.md |
| Delete sessions by filter | `agentsview prune` (use `--dry-run` first) | references/commands.md |
| Import Claude.ai/ChatGPT export | `agentsview import --type ... <path>` | references/commands.md |
| Export summaries/reports | `export sessions`, `export hour\|day\|digest` | references/commands.md |
| Secret leak scan | `secrets scan` / `secrets list` | references/commands.md |
| Semantic (meaning-based) search | `embeddings build`, `--semantic`/`--hybrid` | references/search.md |
| Durable knowledge layer | `recall query/brief/...` | references/search.md |
| Mirror to PostgreSQL | `pg push` / `pg serve` / `pg service` | references/remote-mcp.md |
| Mirror to DuckDB | `duckdb push` / `duckdb serve` | references/remote-mcp.md |
| Expose history to assistants | `agentsview mcp` | references/remote-mcp.md |
| Diagnose sync problems | `agentsview doctor sync` | references/commands.md |
| Config file, data dir, agent dirs | `~/.agentsview/config.toml`, env vars | references/configuration.md |

## Core Workflow

```bash
agentsview version        # what is installed
agentsview sync           # refresh archive (safe, incremental)
agentsview session list --limit 10 --json
```

**Searching history.** Exact identifiers (error strings, paths, tool names) →
substring/FTS search. Conceptual questions ("how did we handle X") → hybrid
semantic search when the embedding index is set up, otherwise several short
FTS probes. See references/sessions.md for modes and fallbacks.

```bash
agentsview session search "exact error text" --fts --json --limit 8
agentsview session search "deploy pipeline flaky" --hybrid --context 2 --json
```

**Inspecting a hit.** A search match is a lead. Center a message window on the
match's ordinal before drawing conclusions:

```bash
agentsview session messages <session-id> --around <ordinal> --before 8 --after 8 --json
```

**Costs.** `usage daily` aggregates cost by day (30-day default window).
`session usage <id>` gives one session's tokens and cost. Both read from the
indexed archive; `--offline` skips the network pricing fetch.

**Deleting.** `prune` requires at least one filter and always preview first:

```bash
agentsview prune --project scratch --max-messages 2 --dry-run
```

## Daemon Model (What Happens Under the Hood)

A detached daemon owns SQLite writes for the data directory. Read-only CLI
commands attach to it when running, otherwise open SQLite read-only directly —
so one-off reads stay fast and scripts never fight over the write lock.
Commands that write or need fresh data (`sync`, `session sync`, `usage`,
`pg push`, `duckdb push`) auto-start the daemon. Consequences:

- Set `AGENTSVIEW_NO_DAEMON=1` in CI/scripts that must never spawn a daemon;
  writes then require acquiring the write-owner lock directly.
- The daemon self-exits after idle timeout (default 20m); long-lived
  integrations should tolerate it restarting.
- If a writable daemon is known but unreachable, write commands refuse rather
  than double-write. Check `agentsview daemon status`.

## Conventions

- Structured commands accept `--format json`; `--json` is the alias. Prefer
  JSON when piping into scripts; human output is tuned for terminal reading.
- Relative time windows use `--since Nh|Nd|Nw|Nm|Ny` — **`m` means calendar
  months, not minutes.** `--date`/`--date-from`/`--date-to` take `YYYY-MM-DD`.
- `--project`, `--agent`, and `--machine` filters apply across most commands.
- One-shot and automated sessions are excluded from `session list` and search
  by default; re-include with `--include-one-shot` / `--include-automated`.
- Session IDs vary by agent: Claude UUIDs (`550e8400-...`), Claude subagents
  (`agent-a86574e`), prefixed forms (`codex:my-session-id`). Copy IDs from
  `session list` output rather than guessing.

## Safety

- Session archives contain prompts, file paths, and possibly credentials.
  Treat output as sensitive; never paste secrets from sessions into examples.
- `secrets list` redacts by default; `--reveal` is localhost-only for a reason.
- `AGENTSVIEW_DATA_DIR` redirects everything (db, config, logs) — useful for
  scratch experiments so the production archive is never touched.
