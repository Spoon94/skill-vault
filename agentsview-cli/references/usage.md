# Usage, Cost & Reporting Reference

Condensed from `docs/token-usage.md`, `docs/activity.md`, and `docs/stats.md`.
Table of contents: [usage daily](#agentsview-usage-daily),
[usage statusline](#agentsview-usage-statusline),
[usage cursor](#agentsview-usage-cursor),
[session usage / token-use](#per-session-usage-session-usage--token-use),
[activity report](#agentsview-activity-report),
[stats](#agentsview-stats),
[pricing notes](#pricing-notes).

## `agentsview usage daily`

Token usage and estimated cost aggregated by local-time day (last 30 days by
default).

```bash
agentsview usage daily                           # last 30 days
agentsview usage daily --all                     # full history
agentsview usage daily --since 14d               # last 14 days
agentsview usage daily --since 2026-04-01 --breakdown
agentsview usage daily --json --agent claude
```

| Flag | Description |
| --- | --- |
| `--format human\|json`, `--json` | output format |
| `--since` / `--until` | duration like `28d` or `YYYY-MM-DD`, inclusive |
| `--all` | full history; overrides the 30-day window |
| `--agent` | filter by agent name |
| `--breakdown` | per-model rows |
| `--offline` | skip the LiteLLM pricing fetch; use embedded fallback |
| `--no-sync` | skip the on-demand sync pass before querying |
| `--timezone` | IANA timezone for date bucketing |

Costs come from per-message token metadata the agents wrote to their logs
(Claude Code, Codex, Copilot CLI, OpenCode and forks, Gemini, Qwen Code, and
many more; coverage is opportunistic — rows contribute only with usable token
counts + a priceable model). Reads from the pre-indexed archive, so it is fast
on large histories (this is the `ccusage`-style question: "what did I spend
yesterday?").

## `agentsview usage statusline`

One line: today's estimated cost. For shell prompts / tmux status lines.

```bash
agentsview usage statusline          # $9.61 today
agentsview usage statusline --json   # {"date": "...", "cost": {"microdollars": 9610000}}
```

Flags: `--format`/`--json`, `--agent`, `--offline`, `--no-sync`.

## `agentsview usage cursor`

Import Cursor Admin API usage events into the archive (billable team usage,
including headless events that may not map to local transcripts). Requires
`cursor_admin_api_key` (and optional `cursor_admin_email` /
`cursor_admin_user_id` defaults) in `~/.agentsview/config.toml`.

```bash
agentsview usage cursor                                  # last 30 days
agentsview usage cursor --since 2026-05-01 --until 2026-05-31
agentsview usage cursor --all --email you@example.com
```

Rows dedupe by stable fingerprint — safe to re-run a window. Imported rows
appear as `agent = cursor`; their costs come from Cursor's `chargedCents`
(not the pricing table), and project/machine/session filters do not apply to
them.

## Per-session usage: `session usage` / `token-use`

```bash
agentsview session usage <id> [--format json]
```

`agentsview token-use <id>` is the deprecated alias (0.30.0+); new scripts
should use `session usage`. Both accept the same session-ID formats.

Key JSON fields: `total_output_tokens`, `peak_context_tokens`,
`has_token_data`, `cost` (integer microdollar object), `has_cost` (false if
any contributing row is unpriced — never a partial total), `cost_source`
(`computed`/`reported`/`mixed`), `models`, `unpriced_models`,
`breakdown_count`, `breakdown` (per-step rows), `server_running`.

Human output:

```
Session:       abc-123
Agent:         claude
Output:        15230
Peak ctx:      84000
Cost:          ~$2.41 (claude-opus-4-7)
```

The leading `~` marks a computed/mixed figure. Unpriced models render
`n/a (unpriced: model-x)`; no token data at all renders `n/a`.

Exit codes (kept from the `token-use` contract): `0` token/cost data present,
`2` session not found, `3` session exists but has neither token data nor cost.
If no server is running the command performs an on-demand sync for the
requested session first.

## `agentsview activity report`

Active time, concurrency, cost, token, breakdown, and session rows for a
resolved date range (same model as the web UI Activity page).

```bash
agentsview activity report --preset day --date 2026-06-20
agentsview activity report --preset week --date 2026-06-20 --json
agentsview activity report --preset custom \
  --from 2026-06-20T14:00:00Z --to 2026-06-20T18:00:00Z --bucket 15m
```

| Flag | Description |
| --- | --- |
| `--preset` | `day`, `week`, `month`, or `custom` |
| `--date` | anchor date for presets (`YYYY-MM-DD`) |
| `--from` / `--to` | RFC3339 instants for `custom` |
| `--timezone` | IANA timezone for bucketing |
| `--bucket` | `5m`, `15m`, `1h`, `1d`, `1w` (default automatic) |
| `--project`, `--agent`, `--machine` | filters |
| `--format` / `--json`, `--no-sync`, `--offline` | output/sync/pricing |

Human output: totals, peak concurrency, top project/model/agent breakdowns,
top sessions. JSON adds the dense bucket timeline and session rows. Unlike
`session list`, Activity includes one-shot sessions by default.

## `agentsview stats`

Experimental window-scoped workspace analytics across sessions and git
activity.

```bash
agentsview stats
agentsview stats --format json --since 2026-04-01 --until 2026-04-15
agentsview stats --agent claude --include-project my-app
```

Flags: `--format`/`--json`, `--since` (default `28d`; duration or date),
`--until` (`YYYY-MM-DD`), `--agent` (default `all`), `--include-project` /
`--exclude-project` (repeatable), `--timezone`.

Caveats: experimental — human output may change; JSON carries
`schema_version: 1` but treat it as a moving surface. Code attribution from
Cursor reads a live machine-local DB (`~/.cursor/ai-tracking/ai-code-tracking.db`
or `AGENTSVIEW_CURSOR_ATTRIBUTION_DB`) — it is not synced, not pushed to
PostgreSQL, and project filters report `status: "unsupported_filter"` for that
source instead of zero. `AGENTSVIEW_GITHUB_TOKEN` enables PR aggregation.

## Pricing Notes

- Costs are estimates from the `model_pricing` table (LiteLLM feed, refreshed
  online) plus `[custom_model_pricing]` overrides in `config.toml`.
- `--offline` uses the embedded fallback pricing.
- Money is represented as integer microdollar objects in JSON
  (`{"microdollars": 2410000}` = $2.41).
- A `reported` cost is an authoritative session total (no `~` prefix);
  `computed`/`mixed` are estimates derived from per-row pricing.
