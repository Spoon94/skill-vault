---
name: semble
description: Use when exploring an unfamiliar codebase, locating where functionality is implemented, or answering "where is X / how does Y work" questions. Run `semble search` instead of grep+read for semantic or exploratory queries — it returns the relevant code chunks directly and uses ~98% fewer tokens. Triggers: "where is", "how does", "find the code that", code exploration, feature lookup.
---

# Semble — Code Search via CLI

Fast semantic code search. Returns the exact chunks you need, ~98% fewer
tokens than grep+read.

## When to use

- Exploring an unfamiliar codebase / answering "where is X" / "how does Y"
- Locating the implementation of a feature, concept, or flow
- Finding code semantically similar to a known location

Prefer `grep` only for exhaustive literal matches or confirming an exact
string. Use `Read` after semble only when a returned chunk doesn't give
enough context.

## Core commands

```bash
# Search by intent or symbol (path defaults to current dir; git URLs ok)
semble search "authentication flow" ./my-project
semble search "save_pretrained" ./my-project
semble search "save model to disk" ./my-project --top-k 10

# Search docs / config / everything (default is code only)
semble search "deployment guide" ./my-project --content docs
semble search "database host port" ./my-project --content config
semble search "authentication" ./my-project --content all

# Find code similar to a known location (file path + line number)
semble find-related src/auth.py 42 ./my-project
```

Indexes are built and cached on first run, and invalidated automatically
when files change.

If `semble` is not on `$PATH`, semble isn't installed in this environment.
Tell the user and suggest installing it with:

```bash
uv tool install semble
```

(Requires [uv](https://docs.astral.sh/uv/).) Until it's installed, fall
back to `grep` + `Read`.

## Workflow

1. Start with `semble search` to find relevant chunks.
2. Use `--content docs` / `config` / `all` when the answer isn't in code.
3. Read full files only when the returned chunk lacks enough context.
4. Use `semble find-related <file> <line> <path>` on a promising result
   to discover related implementations.
5. Fall back to `grep` only for exhaustive literal matches or exact-string
   confirmation.
