# Sequence Diagram Example

A sequence diagram showing a cache-miss request flow.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant W as Web App
    participant API as API Server
    participant C as Cache
    participant DB as Database

    U->>W: GET /data
    W->>API: GET /api/data
    activate API
    API->>C: GET key
    activate C
    C-->>API: miss
    deactivate C
    API->>DB: SELECT
    activate DB
    DB-->>API: rows
    deactivate DB
    API->>C: SET key
    API-->>W: 200 JSON
    deactivate API
    W-->>U: 200 JSON

    Note over U,W: HTTPS
    Note over API,C: TTL = 5min
```

## Key syntax

- `participant Name as Alias` — declare participant with short alias
- `autonumber` — auto-number messages
- `A->>B: msg` — solid arrow with arrowhead
- `A-->>B: msg` — dotted arrow (return)
- `activate A` / `deactivate A` — lifeline activation
- `Note over A,B: text` — note spanning participants
- `loop`, `alt`/`else`, `opt` — control flow blocks

## Common variations

- `actor Name` instead of `participant` — stick figure
- `rect rgb(220,220,255)\n...end` — colored background region
- `loop N times\n...end` — loop block
