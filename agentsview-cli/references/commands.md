# Core Commands Reference

Condensed from `docs/commands.md` (the CLI Reference). Table of contents:
[sync](#agentsview-sync), [serve & daemon](#agentsview-serve--daemon),
[prune](#agentsview-prune), [projects](#agentsview-projects),
[health](#agentsview-health), [version](#agentsview-version),
[import](#agentsview-import), [export sessions](#agentsview-export-sessions),
[export hour/day/digest](#agentsview-export-hourdaydigest),
[secrets](#agentsview-secrets), [skills install](#agentsview-skills),
[doctor & parse-diff](#agentsview-doctor-sync--parse-diff),
[environment variables](#environment-variables).

## `agentsview sync`

Refresh the local SQLite archive from discovered agent session directories.

```bash
agentsview sync            # incremental sync and exit
agentsview sync --full     # full resync (reparse everything)
agentsview sync --target /path/to/shared-folder   # artifact folder exchange
```

| Flag | Description |
| --- | --- |
| `--full` | Force full resync regardless of data version |
| `--target` | Exchange normalized artifacts with a trusted folder |
| `--host`/`--user`/`--port` | Ad hoc SSH sync (deprecated; prefer configured HTTP) |

Remote machines can be declared in `~/.agentsview/config.toml` so a bare
`agentsview sync` covers a fleet:

```toml
[[remote_hosts]]
host = "buildbox.local"          # transport = "ssh" is the default
user = "wes"
port = 2222

[[remote_hosts]]
host = "devbox1"
transport = "http"
url = "http://devbox1.tailnet.ts.net:8080"
token = "remote-token"           # must match the remote daemon's auth_token
```

After syncing, a summary of session/message counts is printed. Use the daemon
unless `AGENTSVIEW_NO_DAEMON=1` forces a direct offline sync. Claude/Codex
roots may also be `s3://` URLs in config (read-only object-storage sources).

## `agentsview serve` & `daemon`

```bash
agentsview serve                    # foreground server, http://127.0.0.1:8080
agentsview serve --background       # detached managed server
agentsview serve status / restart / stop
agentsview daemon start / status / restart / stop
```

Key `serve` flags: `--host` (default 127.0.0.1), `--port` (8080, auto-picks a
free port if busy), `--no-browser`, `--no-sync`, `--require-auth`,
`--replace`, `--public-url` (required when reaching the server through SSH
port-forwarding, a reverse proxy, or a remote dev environment — the server
validates the Host header against it), `--proxy caddy` with `--public-port`.

Notes:

- Plain `agentsview` shows help; the server only starts with `serve`.
- `daemon start`/`restart` take no serve flags — persistent settings belong in
  `config.toml`. For one-off flags (`--no-sync`, non-loopback `--host`), use
  `serve --background`.
- `daemon` commands manage only the writable SQLite daemon; `pg serve` and
  `duckdb serve` processes are ignored by them. `serve stop` stops writable
  and read-only servers.
- Newer release binaries auto-replace an older running daemon; downgrades and
  dev builds need `--replace`. If the archive has a newer data version than
  the binary, `serve` refuses before stopping the old daemon.
- The port-forward/reverse-proxy 403 error is fixed with
  `serve --public-url <exact origin opened in the browser>`.

## `agentsview prune`

Delete sessions matching filters. At least one filter required; filters
combine with AND.

| Flag | Description |
| --- | --- |
| `--project` | Project name substring |
| `--max-messages N` | Sessions with at most N messages |
| `--before YYYY-MM-DD` | Sessions ended before this date |
| `--first-message <text>` | First message starts with this text |
| `--dry-run` | Preview only — always run this first |
| `--yes` | Skip confirmation prompt |

```bash
agentsview prune --project "scratch" --dry-run
agentsview prune --max-messages 2 --before 2025-01-01
```

Prints count deleted and disk reclaimed.

## `agentsview projects`

List all projects with session counts. `--format human|json`.

## `agentsview health`

Session intelligence view (grade + outcome signals).

```bash
agentsview health                  # recent sessions with grade/outcome columns
agentsview health --limit 50
agentsview health <session-id>     # detailed signal counts for one session
agentsview health <id> --json
```

## `agentsview version`

```bash
agentsview version          # e.g. agentsview v0.38.0 (commit ..., built ...)
agentsview version --json   # {schema_version, name, version, commit, build_date}
```

Does not need a daemon, config, or database. Use it to detect an outdated
binary before trusting that a documented command is missing.

## `agentsview import`

Import Claude.ai or ChatGPT exports.

```bash
agentsview import --type claude-ai ~/Downloads/claude.zip
agentsview import --type chatgpt ~/Downloads/chatgpt.zip
agentsview import --type claude-ai ./conversations.json
```

Path may be a `.zip`, a `conversations.json` (Claude.ai only), or an extracted
directory.

## `agentsview export sessions`

Content-free session summaries from the local archive. One-shot and automated
sessions excluded by default (use `--include-one-shot`,
`--include-automated`, `--include-children`).

```bash
agentsview export sessions --format json
agentsview export sessions --format ndjson --limit 100
agentsview export sessions --all --project agentsview --format ndjson
```

Notable flags: `--format json|ndjson`, `--limit` (default/max 500), `--cursor`
(opaque, from a previous page), `--all`, `--project` / `--exclude-project`,
`--machine`, `--git-branch`, `--agent`, `--date` / `--date-from` /
`--date-to`, `--active-since` (RFC3339), `--min-messages` / `--max-messages`,
`--outcome`, `--health-grade`, `--min-tool-failures`, `--has-secret`.

JSON top level: `schema_version` (currently 2), `database_id`, `cursor`,
`pricing`, `projects`, `sessions`. With `--cursor`, only `--format`, `--json`,
and `--limit` may accompany it. An expired cursor exits 4 with a
`cursor_reset` JSON error on stderr.

## `agentsview export hour|day|digest`

Canonical UTC reporting documents:

```bash
agentsview export hour 2026-07-28-13
agentsview export day 2026-07-28
agentsview export digest --from 2026-06-28 --to 2026-07-27
```

Keys are exact zero-padded UTC values; open/future hours are rejected; the
current UTC day has no day digest; digest ranges are inclusive, max 31 dates.
Consumers should validate `schema_version: 1` and the content digest.

## `agentsview secrets`

Secret-leak scanning across sessions (redacted by default).

```bash
agentsview secrets scan              # full ruleset (definite + candidate)
agentsview secrets scan --backfill   # only sessions not scanned at current ruleset
agentsview secrets list              # definite findings, redacted
agentsview secrets list --confidence all --json
agentsview secrets list --reveal     # raw values; localhost daemon only
```

Flags: `--project`, `--agent`, `--date-from`, `--date-to`, `--rule`,
`--confidence definite|candidate|all` (default definite), `--limit`
(default 50, max 500), `--cursor`. The sync-time inline scan only stamps
definite-tier findings; candidate-tier needs an explicit `scan --backfill`.

## `agentsview skills`

Installs the bundled `agentsview-finding-history` skill (teaches coding-agent
harnesses to search session history) — separate from this skill.

```bash
agentsview skills install [--harness claude|agents] [--project] [--force]
agentsview skills list [--project] [--format json]
```

Writes under `~/.claude/skills/` or `~/.agents/skills/` (or the current repo
with `--project`). Overwrites unmodified generated files; refuses hand-edited
or foreign files unless `--force`. `list` shows STATE:
missing/current/stale/modified/foreign.

## `agentsview doctor sync` & `parse-diff`

`doctor sync` is read-only diagnostics for sync problems: data dir and DB
path, readability, `user_version` vs binary data version, the startup sync
decision, session counts by data version, agent roots existence, recent
`debug.log` lines, and a likely-cause summary.

`parse-diff` re-parses sources against the archive for parser QA
(`--agent`, `--limit`, `--fail-on-change`, `--json`). It reports parser drift
separately from `raced`, `incremental_skew`, and `pending_resync` noise; run
a full resync first for a clean baseline.

## Environment Variables

Most-used ones (full table in `docs/commands.md`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTSVIEW_DATA_DIR` | `~/.agentsview` | Data dir: sessions.db, config.toml, serve.log |
| `AGENTSVIEW_NO_DAEMON` | unset | `1` disables daemon auto-start |
| `AGENTSVIEW_DAEMON_IDLE_TIMEOUT` | `20m` | Idle self-shutdown for background daemons |
| `AGENTSVIEW_AUTH_TOKEN` | | Bearer token for `require_auth` |
| `AGENTSVIEW_SERVER_TOKEN` | | Token for an explicit `--server` URL |
| `AGENTSVIEW_PG_URL` / `AGENTSVIEW_PG_MACHINE` / `AGENTSVIEW_PG_SCHEMA` | / / `agentsview` | PostgreSQL sync config |
| `AGENTSVIEW_DUCKDB_PATH` / `_URL` / `_TOKEN` | `~/.agentsview/sessions.duckdb` | DuckDB mirror / Quack read endpoint |
| `AGENTSVIEW_GITHUB_TOKEN` | | Gist publishing, `stats` PR aggregation |
| `AGENTSVIEW_DISABLE_UPDATE_CHECK` | | `1` disables update check |
| `AGENTSVIEW_TELEMETRY_ENABLED` | | `0` disables anonymous telemetry |
| `<AGENT>_DIR` (e.g. `CLAUDE_PROJECTS_DIR`, `CODEX_SESSIONS_DIR`, `CURSOR_PROJECTS_DIR`) | per-agent defaults | Override session discovery roots |

Override inline for scratch work:
`AGENTSVIEW_DATA_DIR=/tmp/av-test agentsview serve`.
