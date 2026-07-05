# Pie Chart Example

A pie chart showing browser market share.

```mermaid
pie showData title Browser Market Share (Q1 2025)
    "Chrome" : 65.3
    "Safari" : 18.2
    "Edge" : 5.4
    "Firefox" : 3.1
    "Samsung Internet" : 2.7
    "Opera" : 2.1
    "Other" : 3.2
```

## Key syntax

- `pie` — diagram type keyword
- `title ...` — chart title
- `showData` (optional) — display numeric values alongside slices
- `"Label" : value` — slice with label and numeric value (relative weights, not percentages)

## Common variations

- `pie title No data labels` — without `showData`, just slices
- Use decimal values like `65.3` — Mermaid normalizes them to 100%
- Labels must be quoted if they contain spaces
- Slice colors are auto-assigned; can be themed via config
