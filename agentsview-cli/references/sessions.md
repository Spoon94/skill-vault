# Session Query Reference

Condensed from `docs/session-api.md` (the `agentsview session` programmatic
surface) and `docs/semantic-search.md`. Table of contents:
[stability & transport](#stability--transport),
[session list](#agentsview-session-list),
[session get / health](#agentsview-session-get),
[session messages](#agentsview-session-messages),
[session search](#agentsview-session-search),
[session tool-calls](#agentsview-session-tool-calls),
[session export / watch](#agentsview-session-export--watch),
[session sync](#agentsview-session-sync).

## Stability & Transport

The JSON output is **additive-only**: new fields appear, existing fields are
never renamed or removed, types are stable. Scripts should ignore unknown
fields. `session export` and `session watch` are the exceptions — they stream
raw bytes / NDJSON and reject `--format`/`--json`.

Common flags on structured commands: `--format human|json`, `--json`,
`--server <url>`, `--server-token-file <path>`, `--pg`.

Transport selection (automatic):

1. `--server <url>` → proxy to that daemon over HTTP. The local config
   `auth_token` is NOT sent to explicit URLs; use `AGENTSVIEW_SERVER_TOKEN`
   or `--server-token-file`. `--server` and `--pg` are mutually exclusive.
2. A local writable daemon running → proxy to it.
3. A read-only `pg serve` daemon → reads proxy to it, but `session sync`
   refuses.
4. Nothing running → read-only commands open SQLite directly (fast);
   write/fresh commands auto-start a detached daemon.
5. `AGENTSVIEW_NO_DAEMON=1` → never auto-start; reads use direct read-only
   SQLite, writes require the write-owner lock.

`--pg` reads from configured PostgreSQL (read-only; `session sync` and
`session export` reject it). Configured `AGENTSVIEW_PG_URL` alone does not
change the default read path — reads stay on local SQLite unless `--pg` is
given.

## `agentsview session list`

Filtered, paginated session list. One-shot and automated sessions are
excluded by default.

```bash
agentsview session list --limit 10 --json
agentsview session list --resume          # active in last 15 minutes
agentsview session list --project myapp --since 3d
agentsview session list --sort messages:desc,started:asc
```

Human output is resume-oriented: full ID, age, agent, project, branch, message
count, title, working directory, plus a marker on sessions active in the last
15 minutes.

Key flags:

| Flag | Notes |
| --- | --- |
| `--project` / `--exclude-project` | string |
| `--machine`, `--agent` | string |
| `--date`, `--date-from`, `--date-to` | `YYYY-MM-DD`; overlaps count |
| `--active-since` | RFC3339 timestamp |
| `--since` | Relative `Nh/Nd/Nw/Nm/Ny` (m=months!) or `YYYY-MM-DD`; exclusive with `--active-since` |
| `--resume` / `--active` | Last 15 minutes |
| `--min-messages`, `--max-messages`, `--min-user-messages` | int |
| `--include-one-shot`, `--include-automated`, `--include-children` | re-include defaults-excluded |
| `--outcome`, `--health-grade` | comma-separated |
| `--min-tool-failures` | int; `0` is meaningful |
| `--has-secret` | only sessions with definite secret findings |
| `--sort` | keys below, optional `:asc`/`:desc` |
| `--reverse` / `-r` | flip default direction |
| `--cursor`, `--limit` | pagination; limit default 200, max 500 |

Sort keys: `recent` (default desc), `started`, `messages`, `user-messages`,
`output-tokens`, `peak-context`, `failures`, `retries`, `edit-churn`,
`compactions`, `context-pressure`, `health`, `secrets`, `id`.

JSON: `{"sessions": [...], "next_cursor": "...", "total": N}`. When the first
page hides one-shot/automated sessions, a stderr advisory names the flags to
reveal them; stdout/JSON shape is unchanged.

## `agentsview session get`

Metadata + computed signals for one session.

```bash
agentsview session get <id> [--format json]
```

Fields include `id`, `project`, `machine`, `agent`, `first_message`,
`display_name`, `git_branch`, `started_at`, `ended_at`, `message_count`,
`user_message_count`, `health_score`, `health_grade`, `outcome`,
`health_score_basis`, `health_penalties`, `parser_malformed_lines`,
`secret_leak_count`. `health_score_basis`/`health_penalties` populate when
`health_score` is non-null. `git_branch` is omitted when the source has none.

Session ID formats vary by agent: Claude root sessions use UUIDs, Claude
subagents use `agent-<hex>`, and some agents prefix (e.g. `codex:<id>`). Raw
agent-emitted IDs are accepted when resolvable.

## `agentsview session messages`

Paginated message window.

```bash
agentsview session messages <id> --from 0 --limit 20 --json
agentsview session messages <id> --direction desc --limit 10
agentsview session messages <id> --around 19 --before 8 --after 8 --role user,assistant --json
```

- `--from` omitted = start at beginning (asc) or newest page (desc); explicit
  `--from 0` = ordinal 0 in both directions.
- `--around N` centers a window on ordinal N (mutually exclusive with
  `--from`/`--direction`); `--before`/`--after` default 5 each and count
  filtered messages when `--role` is set; the anchor is always included.
- Responses report `first_ordinal`/`last_ordinal` so callers continue with
  `--from <last_ordinal + 1>`.
- Each message: `ordinal`, `role`, `content`, `thinking_text`, `timestamp`,
  `is_system`, `source_type`, `source_subtype`, `has_thinking`, `has_tool_use`.
  Promoted `source_subtype` on system messages: `continuation`, `resume`,
  `interrupted`, `task_notification`, `stop_hook`, `compact_boundary`.

## `agentsview session search`

Search message bodies, tool inputs, and tool result content.

```bash
agentsview session search "database timeout" --json --limit 10
agentsview session search "panic" --regex
agentsview session search "deploy flaky" --fts
agentsview session search "how did we handle auth" --hybrid --context 2
```

Modes (mutually exclusive): default substring, `--regex` (RE2), `--fts`
(tokenized FTS5, messages-only, fastest on large archives), `--semantic`
(vectors, messages-only), `--hybrid` (semantic + FTS fusion, messages-only).
Substring and regex also walk tool inputs/results; FTS/semantic/hybrid are
messages-only.

`--semantic`/`--hybrid` require the opt-in embedding index (see search.md)
and return one ranked page (`--cursor` rejected). `--scope top|all|subordinate`
(default `all`) is valid only in those modes and supersedes
`--include-children`.

Other flags: `--context N` (messages before/after, max 10), `--in
messages,tool_input,tool_result` (default all), `--exclude-system`, `--reveal`
(unmask secrets; localhost-only), plus the usual `--project`, `--agent`,
`--machine`, date flags, `--include-*`, `--limit` (default 50, max 500),
`--cursor`.

Every match carries a conversation-unit citation: `ordinal_range` `[start,end]`
(always present; `[ordinal, ordinal]` when the match is its own unit) with
`ordinal` as the anchor, plus lineage fields `subordinate`, `relationship`,
`parent_session_id`, `is_sidechain`. Only lineage fields are `omitempty`;
`score` appears only in semantic/hybrid. Snippets carry ~60 chars of context
each side; substrings matching the secret ruleset are masked unless
`--reveal`.

One-shot, automated, and subagent sessions excluded by default; opt back in
with the `--include-*` flags.

## `agentsview session tool-calls`

Chronological flattened tool invocations.

```bash
agentsview session tool-calls <id> [--format json]
```

Rows: `ordinal`, `timestamp`, `tool_use_id`, `tool_name`, `category`,
`input_json` (a string — serialized JSON or a plain string), `skill_name`,
`subagent_session_id`, `result_length`.

## `agentsview session export` & `watch`

`session export <id>` streams the raw source file (e.g. JSONL) to stdout.
Local-only: rejects `--server`, `--pg`, and `--format`/`--json`. Exits 1 with
`source file not found` / `session not in local archive` messages when the
file or session is missing.

`session watch <id>` streams NDJSON events (`session_updated`, `heartbeat`)
until Ctrl+C. Unknown IDs fail fast rather than streaming heartbeats forever.

## `agentsview session sync`

Parse and insert a single session; blocks until indexing + signal computation
finish.

```bash
agentsview session sync ./session.jsonl     # parse a raw file
agentsview session sync <session-id>        # re-parse an archived session
```

If the argument is an existing filesystem path it is parsed as a file;
otherwise treated as a session ID. When one file maps to multiple sessions
(forked/resumed branches) the command refuses and lists candidate IDs — then
re-run with a specific `<id>`. Uses a writable daemon when running, starts one
when needed, and refuses under a read-only `pg serve` daemon. With
`AGENTSVIEW_NO_DAEMON=1` it runs in-process after acquiring the write lock.
