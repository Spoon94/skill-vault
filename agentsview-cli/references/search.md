# Semantic Search & Recall Reference

Condensed from `docs/semantic-search.md` and `docs/recall.md`. Table of
contents: [enabling semantic search](#enabling-semantic-search-vector),
[building the index](#building-the-index),
[searching](#searching-semantic--hybrid),
[hit shape & cursor-follow](#hit-shape--cursor-follow),
[recall](#agentsview-recall-experimental).

Semantic search is **opt-in and disabled by default**. FTS and substring
search work without it — see sessions.md for those modes and their fallbacks.

## Enabling Semantic Search (`[vector]`)

Add a `[vector]` section to `~/.agentsview/config.toml`:

```toml
[vector]
enabled = true                    # default false
# db_path defaults to <data_dir>/vectors.db

[vector.embeddings]
model = "nomic-embed-text"
dimension = 768                   # every vector must have this length
query_prefix = "search_query: "    # prepended to queries only (model-dependent)
document_prefix = "search_document: "
default_server = "local"

[vector.embeddings.servers.local]
endpoint = "http://localhost:11434/v1"  # OpenAI-compatible; "/embeddings" appended
api_key_env = "OPENAI_API_KEY"    # env var name holding the key; omit if anonymous
batch_size = 32
concurrency = 4
timeout = "30s"
max_retries = 3

[vector.embed]
run_after_sync = true             # daemon embeds deltas after each sync
backstop_interval = "24h"         # periodic reconciliation; negative disables
```

`model`, `dimension`, and at least one server with an `endpoint` are required
once enabled; agentsview fails fast with an actionable message otherwise.
Restart the daemon (or run a CLI command) after editing. With Ollama, pull the
model first (`ollama pull nomic-embed-text`). Model identity (model,
dimension, prefixes) is global across all servers; per-server settings are
transport/capacity only.

## Building the Index

```bash
agentsview embeddings build            # build or refresh
agentsview embeddings build --using build-box   # one build on another server
agentsview embeddings list             # list generations
agentsview embeddings activate <id>    # activate a generation
agentsview embeddings retire <id>      # retire a generation
```

Requires `[vector]` enabled. A generation is a fingerprinted set of embeddings
for one model/dimension; activate exactly one generation to serve. The daemon
embeds sync deltas automatically when `run_after_sync = true`. For PostgreSQL
maintenance, use `agentsview pg vectors list` / `pg vectors drop <id>`.

## Searching: `--semantic` / `--hybrid`

```bash
agentsview session search "how do we handle rate limits" --semantic --json
agentsview session search "deploy pipeline flaky" --hybrid --context 2 --json --limit 8
agentsview session search "auth decisions" --hybrid --scope top --since 3m
```

- `--semantic`: vector search over user/assistant messages. `--hybrid`:
  semantic + FTS reciprocal-rank fusion. Both are messages-only and need the
  active embedding index.
- `--scope top|all|subordinate` (default `all`) includes/excludes sidechain
  and subagent content; it supersedes `--include-children` in these modes and
  is rejected outside them.
- Semantic/hybrid return one ranked page; `--cursor` is rejected. Each hit has
  a `score` plus the standard `ordinal_range` citation and lineage fields.
- Concept questions work best with a focused phrase in hybrid mode. If you
  get "semantic search not available" (no index), fall back to several short
  FTS probes. "Temporarily unavailable" means the embeddings endpoint is down
  — retry once, then say so rather than silently downgrading.

## Hit Shape & Cursor-Follow

Every match (all modes) carries `ordinal_range` `[start, end]` — the
conversation unit containing the match — with `ordinal` as the exact anchor
message. Subagent/sidechain hits carry `subordinate`, `relationship`,
`parent_session_id`, `is_sidechain`; treat them as supporting evidence and
corroborate against the parent before citing a decision.

To read the conversation around a hit, center a window on the anchor:

```bash
agentsview session messages <session-id> --around <ordinal> --before 8 --after 8 --role user,assistant --json
```

## `agentsview recall` (Experimental)

A durable-knowledge layer over the local session archive. Active research —
the corpus may need rebuilding as schema/scoring/trust policy evolve.
Local and SQLite-only; not served via PostgreSQL/DuckDB.

```bash
agentsview recall list
agentsview recall get <id>
agentsview recall query <text> [--mode lexical|vector|hybrid]
agentsview recall brief <task>
agentsview recall stats
agentsview recall extract run [--session <id>] [--full] [--limit <n>]
agentsview recall extract status
agentsview recall extract activate
agentsview recall extract retire <fingerprint> [--force]
agentsview recall extract doctor
agentsview recall extract preview --session <id>
agentsview recall import <accepted-recall.jsonl> --dry-run
```

- `query`/`brief` accept `--mode lexical` (default), `vector`, or `hybrid`.
  Vector/hybrid need the separate Recall embedding store:
  `agentsview embeddings build --store recall` (automatic Recall embedding
  needs `[vector.embed] recall = true`). They fail closed when the corpus is
  newer than the last completed build.
- Model-backed extraction needs an enabled `[recall.extract]` config section.
  Extraction subcommands are local-only and refuse `--server`; while a daemon
  owns the archive it runs extraction itself and manual
  `run`/`activate`/`retire` are refused.
- Import is a guarded laboratory inlet: use an isolated `AGENTSVIEW_DATA_DIR`,
  run `--dry-run` first; a write needs `--yes`, a remote write needs
  `--allow-remote-import`, and the default production directory is refused
  unless `--allow-production-import` is given. These flags do not bypass
  trust/evidence checks.
- With `--server <url>`, provide credentials via `AGENTSVIEW_SERVER_TOKEN` or
  `--server-token-file`; the local daemon token is never sent.
