# Remote Mirrors & MCP Reference

Condensed from `docs/pg-sync.md`, `docs/duckdb.md`, and `docs/mcp.md`. Table
of contents: [pg push](#agentsview-pg-push), [pg status/serve](#pg-status-and-pg-serve),
[pg service](#agentsview-pg-service), [pg vectors](#agentsview-pg-vectors),
[duckdb](#agentsview-duckdb), [mcp server](#agentsview-mcp).

## `agentsview pg push`

Sync sessions from local SQLite to PostgreSQL. Configure first in
`~/.agentsview/config.toml`:

```toml
[pg]
url = "postgres://user:pass@host:5432/dbname?sslmode=require"
machine_name = "my-laptop"   # defaults to hostname; must not be "local"
```

For multiple destinations use named `[pg.NAME]` blocks plus `default_pg`
(`all`, `local`, and legacy field names are reserved as target names).

```bash
agentsview pg push                    # one-shot sync of all sessions
agentsview pg push --watch            # keep current: push on change + periodic floor
agentsview pg push --all              # push every configured target
agentsview pg push --projects a,b     # only these projects
```

| Flag | Default | Description |
| --- | --- | --- |
| `--full` | `false` | Force full local resync and re-push |
| `--no-vectors` | `false` | Skip the semantic-search vector phase |
| `--projects` / `--exclude-projects` | | Comma-separated include/exclude |
| `--all-projects` | `false` | Ignore configured project filters this run |
| `--all` | `false` | Push every configured target sequentially |
| `--watch` | `false` | Run continuously |
| `--debounce` | `30s` | Coalesce window after change (`--watch` only) |
| `--interval` | `15m` | Periodic floor push interval (`--watch` only) |

The schema is created automatically on first push. Project filtering
interacts with the push watermark — see `docs/pg-sync.md` before combining
filters with incremental pushes.

## `pg status` and `pg serve`

```bash
agentsview pg status [target] [--all] [--projects a,b]
agentsview pg serve [serve flags]      # read-only web UI backed by PostgreSQL
```

`pg serve` accepts the same serve flags (`--host`, `--port`, `--proxy`, TLS)
plus PG configuration from `config.toml`. No local SQLite, file watching, or
uploads — viewer only. When the host's `[vector]` config matches a pushed
generation, semantic/hybrid search is served from pgvector.

## `agentsview pg service`

Install and manage the background auto-push service (runs `pg push --watch`).
Service managers: launchd on macOS, `systemd --user` on Linux.

```bash
agentsview pg service install      # generate unit, enable, start
agentsview pg service status       # service status + last successful push
agentsview pg service logs [-f]    # follow pg-watch.log in the data dir
agentsview pg service start / stop
agentsview pg service uninstall
```

## `agentsview pg vectors`

Inspect/drop embedding generations stored in PostgreSQL:

```bash
agentsview pg vectors list [--target NAME]
agentsview pg vectors drop <id> [--target NAME] [--yes]
```

`list` shows model, dimension, document/chunk counts, contributing machines.
`drop` prompts for confirmation unless `--yes`.

## `agentsview duckdb`

Mirror local SQLite into a DuckDB file and serve from it, locally or over the
Quack remote protocol.

```bash
agentsview duckdb push            # mirror SQLite into sessions.duckdb
agentsview duckdb status          # mirror sync status
agentsview duckdb serve           # read-only web UI from the mirror
agentsview duckdb push --watch    # keep the mirror current
agentsview duckdb quack serve --bind quack:127.0.0.1:9494 --token "$TOKEN"
```

`duckdb push` accepts the same `--full` / `--projects` / `--exclude-projects`
/ `--all-projects` / `--watch` / `--debounce` / `--interval` flags as
`pg push`. It always writes the local mirror at `[duckdb].path` and never
targets a remote endpoint — if `[duckdb].url` or `AGENTSVIEW_DUCKDB_URL` is
set, push fails and tells you to unset it and use `quack serve` instead.
`duckdb status` and `duckdb serve` read the remote Quack endpoint when a URL
is configured, the local mirror otherwise. Client URLs use the
`quack:HOST:PORT` authority form (`quack:http://...` is rejected).
Unavailable on Windows ARM64 (no upstream prebuilt bindings).

Quack consumer side:

```bash
AGENTSVIEW_DUCKDB_URL='quack:127.0.0.1:9494' \
AGENTSVIEW_DUCKDB_TOKEN="$TOKEN" \
agentsview duckdb serve
```

## `agentsview mcp`

Read-only Model Context Protocol server exposing session history to assistant
clients (Claude Desktop, Claude Code, Codex, ...).

```bash
agentsview mcp                                  # stdio (default, preferred)
agentsview mcp --server http://127.0.0.1:8080   # explicit daemon
agentsview mcp --http 127.0.0.1:8085            # StreamableHTTP mode
agentsview mcp --pg                             # read from configured PostgreSQL
```

Client config (stdio):

```json
{
  "mcpServers": {
    "agentsview": { "command": "agentsview", "args": ["mcp"] }
  }
}
```

For an authenticated remote daemon:

```json
"args": ["mcp", "--server", "https://agents.example.com",
         "--server-token-file", "/Users/me/.agentsview/token"]
```

Exposed tools: `search_sessions`, `list_sessions`, `get_session_overview`,
`get_messages`, `search_content` (substring/regex/semantic/hybrid modes, plus
`scope` for semantic/hybrid), `get_usage_summary`.

Operational notes:

- Local stdio mode is daemon-backed: each tool call resolves the local daemon
  and starts it when needed. It never opens SQLite directly; if you set
  `AGENTSVIEW_NO_DAEMON=1`, use `--server` against an explicitly started
  daemon instead.
- `--http` binds loopback by default (`8085` and `:8085` mean
  `127.0.0.1:8085`); non-loopback binds require `--http-allow-insecure` plus
  a configured bearer token.
- The local config `auth_token` is never sent to explicit `--server` URLs —
  provide `AGENTSVIEW_SERVER_TOKEN` or `--server-token-file` instead.
- MCP exposes prompts, tool output, paths, and usage totals: treat it like
  access to the archive itself.
