# Context-isolated search (PTC pattern)

Search the web, filter results, and extract content so that **raw search data never enters your context window**. Only your curated `print()` output comes back.

## Why this matters

A typical `tvly search --include-raw-content` returns 8 results × 30-50K chars each = **~300K characters** of raw page content. If this enters your context window, you burn tokens reading navigation bars, cookie banners, and boilerplate — and your reasoning quality degrades under the noise. By processing results inside a Python script, only your `print()` output enters context — typically **1-3K characters** of pure signal. That's a 100-200x reduction.

## Background: Programmatic Tool Calling (PTC)

This pattern replicates [Anthropic's Programmatic Tool Calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) for web search. PTC lets the model write code that orchestrates tool calls inside a sandbox — intermediate results stay in the sandbox, and only the final `print()` output reaches the model's context window. Here, the Python process is the sandbox; variables in memory hold the raw data; only what you `print()` crosses into your context window.

## Core rule

**NEVER** run `tvly` as a bare command in this mode. Always process output through Python so you control what enters your context.

```bash
# WRONG — raw results flood your context
tvly search "quantum computing 2025" --json

# RIGHT — only your print() output enters context
tvly search "quantum computing 2025" --json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
for r in data['results']:
    print(f'[{r[\"score\"]:.2f}] {r[\"title\"]}')
    print(f'  {r[\"url\"]}')
"
```

## JSON Schemas

You need these to write correct filtering code.

### tvly search --json

```json
{
  "query": "string",
  "answer": "string | null",
  "results": [
    {
      "url": "string",
      "title": "string",
      "content": "string (snippet, ~500-1500 chars)",
      "score": 0.0-1.0,
      "raw_content": "string | null (full page, only with --include-raw-content)"
    }
  ],
  "response_time": 0.0
}
```

### tvly extract --json

```json
{
  "results": [
    {
      "url": "string",
      "title": "string",
      "raw_content": "string (full page markdown)",
      "images": []
    }
  ],
  "failed_results": [],
  "response_time": 0.0
}
```

## Execution modes

### Pipe mode — for simple filters (3-5 lines)

Pipe `tvly` output into `python3 -c`:

```bash
tvly search "query" --json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
# your filtering code here
"
```

### Heredoc mode — for anything more complex

Single Bash call, clean multi-line Python, no escaping, no temp files:

```bash
python3 << 'PYEOF'
import json, subprocess
raw = subprocess.check_output(
    ['tvly', 'search', 'query', '--json'],
    stderr=subprocess.DEVNULL
)
data = json.loads(raw)
for r in data['results']:
    print(f"[{r['score']:.2f}] {r['title']}")
    print(f"  {r['url']}")
PYEOF
```

Single-quoted heredocs (`<< 'PYEOF'`) don't interpret anything — no escaping needed.

### Script mode — only when you will reuse the same script across multiple turns

Do NOT write one-shot scripts to `/tmp/`. If you run it once, use a heredoc.

**Important: save DATA to `/tmp/`, not CODE.** Writing `/tmp/tavily_results.json` (data for later turns) = good. Writing `/tmp/my_filter.py` (one-shot code) = wasteful — use a heredoc instead.

## Multi-turn iteration

For complex queries, you often need to **explore before you extract** — search, see titles, decide which results to drill into, then extract. The key: **save raw results to a file, then process them in separate steps.** The file is your persistent state between turns.

### Turn 1: Search and explore

```bash
python3 << 'PYEOF'
import json, subprocess

raw = subprocess.check_output(
    ['tvly', 'search', 'solid-state battery commercialization 2025',
     '--include-raw-content', 'markdown', '--max-results', '8', '--json'],
    stderr=subprocess.DEVNULL
)
data = json.loads(raw)

with open('/tmp/tavily_results.json', 'w') as f:
    json.dump(data, f)

print(f'{len(data["results"])} results saved to /tmp/tavily_results.json\n')
for i, r in enumerate(data['results']):
    print(f'[{i}] [{r["score"]:.2f}] {r["title"][:90]}')
    print(f'    {r["url"]}')
    print(f'    {r["content"][:150]}')
    print()
PYEOF
```

Context receives: ~800 tokens of titles + snippets. The 300K of raw page content is in `/tmp/tavily_results.json`, untouched.

### Turn 2: Extract based on what you saw

```bash
python3 << 'PYEOF'
import json

data = json.load(open('/tmp/tavily_results.json'))

for i in [0, 2, 5]:
    r = data['results'][i]
    raw = r.get('raw_content', '') or ''
    if not raw:
        continue

    print(f'## {r["title"]}')
    print(f'URL: {r["url"]}\n')

    for para in raw.split('\n\n'):
        para = para.strip()
        if len(para) > 80 and any(kw in para.lower() for kw in
                ['toyota', 'quantumscape', 'samsung', 'commercializ', 'production']):
            print(para)
            print()

    print('---\n')
PYEOF
```

Context receives: ~600 tokens of targeted content. You made the decision about what to keep.

### Turn 3 (optional): Fetch more detail

```bash
python3 << 'PYEOF'
import json, subprocess

raw = subprocess.check_output(
    ['tvly', 'extract', 'https://example.com/article', '--json'],
    stderr=subprocess.DEVNULL
)
data = json.loads(raw)
page = data['results'][0]
content = page.get('raw_content', '')

with open('/tmp/page_detail.txt', 'w') as f:
    f.write(content)

for line in content.split('\n'):
    if any(kw in line.lower() for kw in ['timeline', '2025', '2026', 'mass production']):
        print(line.strip())
PYEOF
```

### When to use multi-turn vs single-turn

**Single turn** (pipe mode or one script): when you know upfront what you're looking for. Specific factual queries, known keywords.

**Multi-turn** (save + explore + extract): when you need to see what's available before deciding what to extract. Open-ended research, complex topics, queries where you don't know the right keywords yet.

## Writing your filtering code

The Python you write IS the filtering logic. There are no fixed templates — you write code that makes sense for the specific query. Here are principles, not rules:

**Triage first.** Inspect titles and scores before fetching full pages. Don't extract everything blindly.

**Be specific.** A financial query should filter for numbers and financial terms. A technical query should look for code blocks and specifications. A news query should look for dates and quotes. Match your filtering to the query.

**Structural filtering helps.** Skip lines shorter than ~50-80 chars (usually nav elements). Skip common boilerplate phrases. Keep headings and their following paragraphs. But these are starting points — adapt based on what you see.

**Print structured output.** Format your output so it's easy to reason over:

```python
print(f'## {title}')
print(f'URL: {url}')
print(relevant_content)
print()
```

**Handle errors.** Pages fail, URLs 404, extractions timeout. Use try/except and skip failures:

```python
try:
    raw = subprocess.check_output(['tvly', 'extract', url, '--json'],
                                   stderr=subprocess.DEVNULL, timeout=30)
except Exception:
    continue
```

**Token budget awareness.** Your `print()` output is what enters your context. Target 150-600 tokens per source. If you're printing 5000+ chars from a single page, you're probably not filtering enough. But if a source has a critical data table, it's fine to keep more.

## Options

All standard `tvly search` options work (see [search.md](search.md)):

| Option | Description |
|--------|-------------|
| `--max-results` | Number of results (default: 5, max: 20) |
| `--depth` | `ultra-fast`, `fast`, `basic` (default), `advanced` |
| `--time-range` | `day`, `week`, `month`, `year` |
| `--include-domains` | Comma-separated whitelist |
| `--exclude-domains` | Comma-separated blacklist |
| `--include-raw-content` | Full page content (`markdown` or `text`) |
| `--country` | Boost results from country |

## Fallback: jq

When `python3` is unavailable, use `jq` for basic filtering:

```bash
tvly search "query" --json 2>/dev/null | jq '[.results[] | select(.score > 0.5) | {title, url, content}]'
```

jq can't do multi-step search-then-extract or complex filtering. Use it only for simple lookups.

## See also

- [search.md](search.md) — bare `tvly search` (use when context size isn't a concern)
- [extract.md](extract.md) — `tvly extract` for the drill-in step
