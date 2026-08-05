# Configuration Reference

Condensed from `docs/configuration.md`. Focused on what a CLI user needs to
know to point agentsview at the right session sources and tune runtime
behavior. Table of contents: [data directory](#data-directory),
[config file](#config-file), [session discovery](#session-discovery),
[env var overrides](#environment-variable-overrides),
[auth & remote access](#auth--remote-access),
[telemetry & updates](#telemetry--updates).

## Data Directory

All persistent state lives under one directory, default `~/.agentsview/`:

```
~/.agentsview/
├── sessions.db        # SQLite archive (WAL mode)
├── vectors.db        # semantic-search index (when [vector] enabled)
├── config.toml       # configuration (auto-created on first run)
├── config.toml.lock  # serializes concurrent config writers
├── db.write.lock     # per-data-dir SQLite write-owner lock
├── serve.log         # detached daemon log
└── uploads/          # uploaded session files
```

Override with `AGENTSVIEW_DATA_DIR` (legacy `AGENT_VIEWER_DATA_DIR` still
accepted as a fallback when unset). Redirecting this is the cleanest way to
run scratch experiments without touching the production archive:

```bash
AGENTSVIEW_DATA_DIR=/tmp/av-test agentsview serve
```

## Config File

`~/.agentsview/config.toml`, auto-created on first run. The format migrated
from JSON to TOML; existing `config.json` is migrated to `config.toml` on
first run (original renamed to `config.json.bak`).

Most-used top-level keys:

| Key | Purpose |
| --- | --- |
| `require_auth` | Require a bearer token for API access; needed for any non-loopback bind |
| `auth_token` | Auto-generated 256-bit bearer token; override with `AGENTSVIEW_AUTH_TOKEN` |
| `host` | Interface to bind (default `127.0.0.1`); non-loopback requires `require_auth = true` |
| `public_url`, `public_origins` | Public origin for Host-header validation / trusted CORS origins |
| `daemon_idle_timeout` | Idle self-shutdown for detached daemons (default `20m`; `"0s"` keeps alive) |
| `cursor_admin_api_key` / `cursor_admin_email` / `cursor_admin_user_id` | Cursor Admin usage import defaults |
| `github_token` | Gist publishing + `stats` PR aggregation |
| `result_content_blocked_categories` | Tool categories whose result content is not stored (default `["Read", "Glob"]`) |
| `chart_palette` | `"agentsview"` (default) or `"matplotlib"` |
| `disable_update_check` | Disable the automatic update check |

Section tables (each links to its deeper doc):

- `[pg]` / `[pg.NAME]` + `default_pg` - PostgreSQL sync (see remote-mcp.md)
- `[duckdb]` - DuckDB mirror (remote-mcp.md)
- `[vector]` + `[vector.embeddings]` / `[vector.embeddings.servers.<name>]` /
  `[vector.embed]` - semantic search (search.md)
- `[recall.extract]` - model-backed recall extraction (search.md)
- `[[remote_hosts]]` - fleet sync (commands.md)
- `[[session_sources]]` - additional filesystem roots with machine labels
- `[automated]` - custom automated-session patterns
- `[custom_model_pricing]` - per-model price overrides for usage reports
- `[proxy]` - managed Caddy proxy (remote-access docs)

`daemon start` / `daemon restart` load this file and accept no serve-specific
flags; `--no-sync` is runtime-only and cannot be stored.

## Session Discovery

agentsview auto-discovers sessions from each supported agent's default
directory. Override a single root with an env var, or scan multiple roots
per agent with array fields in `config.toml`.

Common defaults (env var -> default path):

| Env var | Default | Agent |
| --- | --- | --- |
| `CLAUDE_PROJECTS_DIR` | `~/.claude/projects` | Claude Code |
| `CODEX_SESSIONS_DIR` | `~/.codex/sessions` | Codex |
| `CURSOR_PROJECTS_DIR` | `~/.cursor/projects` | Cursor |
| `GEMINI_DIR` | `~/.gemini` | Gemini CLI |
| `COPILOT_DIR` | `~/.copilot` | Copilot CLI |
| `FORGE_DIR` | `~/.forge` | Forge |
| `GROK_DIR` | `~/.grok/sessions` | Grok |
| `ANTIGRAVITY_DIR` / `ANTIGRAVITY_CLI_DIR` | `~/.gemini/antigravity` / `-cli` | Antigravity IDE / CLI |
| `QWEN_PROJECTS_DIR` | `~/.qwen/projects` | Qwen Code |
| `WARP_DIR` | (platform-specific) | Warp |
| `ZED_DIR` | (platform-specific) | Zed |
| `AIDER_DIR` | (no default; opt-in) | Aider |

The full table (60+ agents) is in `docs/commands.md` under "Environment
Variables" and `docs/configuration.md` under "Session Discovery".

Multiple directories per agent (e.g. Windows + WSL side by side):

```toml
claude_project_dirs = [
  "~/.claude/projects",
  "/mnt/c/Users/you/.claude/projects",
]
codex_sessions_dirs = ["~/.codex/sessions"]
```

Each `<agent>_dirs` array takes precedence over the single-dir env var and the
default path. All listed directories are discovered, watched, and synced
independently.

Machine-labeled filesystem sources (a root produced on another machine,
transported to this host):

```toml
[[session_sources]]
agent = "copilot"
dir = "/srv/session-archive/buildbox/copilot"
machine = "buildbox"   # optional; defaults to local hostname
```

Machine attribution is captured at first ingest; changing an entry's
`machine` affects newly discovered sessions only - ordinary syncs (including
`--full`) do not relabel existing sessions.

Claude and Codex roots may also be `s3://` URLs in `claude_project_dirs` /
`codex_sessions_dirs` for read-only object-storage sources; agentsview uses
object size and `LastModified` to skip unchanged sessions.

## Environment Variable Overrides

The highest-precedence CLI knobs (full table in `docs/commands.md`):

| Variable | Purpose |
| --- | --- |
| `AGENTSVIEW_DATA_DIR` | Redirect the whole data directory |
| `AGENTSVIEW_NO_DAEMON` | `1` disables daemon auto-start (CI/scripts) |
| `AGENTSVIEW_DAEMON_IDLE_TIMEOUT` | Override idle self-shutdown (default `20m`) |
| `AGENTSVIEW_AUTH_TOKEN` | Bearer token for `require_auth` (overrides config) |
| `AGENTSVIEW_SERVER_TOKEN` | Token for an explicit `--server` URL |
| `AGENTSVIEW_PG_URL` / `_MACHINE` / `_SCHEMA` | PostgreSQL sync config |
| `AGENTSVIEW_DUCKDB_PATH` / `_URL` / `_TOKEN` | DuckDB mirror / Quack endpoint |
| `AGENTSVIEW_GITHUB_TOKEN` | Gist publishing, `stats` PR aggregation |
| `AGENTSVIEW_CURSOR_ATTRIBUTION_DB` | Override Cursor attribution DB path for `stats` |
| `AGENTSVIEW_DISABLE_UPDATE_CHECK` | `1` disables update check |
| `AGENTSVIEW_TELEMETRY_ENABLED` | `0` disables anonymous telemetry |

Env vars override config-file defaults. The `<AGENT>_DIR` family overrides
per-agent discovery roots.

## Auth & Remote Access

- Default bind is loopback (`127.0.0.1`) with no auth. Local-only use needs
  nothing here.
- Any non-loopback `host` (or a proxy/reverse-proxy/SSH-forwarded reach)
  requires `require_auth = true` plus a bearer token. The browser login
  prompt accepts `auth_token`.
- For SSH port-forwarding / reverse proxy / remote dev environments
  (Codespaces, Coder, WSL2, exe.dev), start the server with
  `--public-url <exact origin opened in the browser>` so the Host-header
  check passes - otherwise API requests return 403.
- The local config `auth_token` is never sent to an explicit `--server` URL;
  use `AGENTSVIEW_SERVER_TOKEN` or `--server-token-file` for remote daemons.

## Telemetry & Updates

- Anonymous daemon telemetry is on by default; disable with
  `AGENTSVIEW_TELEMETRY_ENABLED=0`.
- Automatic update checks run unless disabled with
  `AGENTSVIEW_DISABLE_UPDATE_CHECK=1` or `disable_update_check = true` in
  config.
- Cursor code-attribution reads a live machine-local DB
  (`~/.cursor/ai-tracking/ai-code-tracking.db` or
  `AGENTSVIEW_CURSOR_ATTRIBUTION_DB`); it is not synced, not pushed to
  PostgreSQL, and project filters report `status: "unsupported_filter"` for
  that source.
