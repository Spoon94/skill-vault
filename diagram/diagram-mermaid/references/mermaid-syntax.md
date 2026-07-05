# Mermaid Full Syntax Reference

Loaded on-demand when the master SKILL.md doesn't have enough detail. For the most up-to-date and complete syntax, see https://mermaid.js.org/intro/.

## Table of Contents

1. [Flowchart](#flowchart)
2. [Sequence Diagram](#sequence-diagram)
3. [Class Diagram](#class-diagram)
4. [State Diagram](#state-diagram)
5. [ER Diagram](#er-diagram)
6. [Gantt Chart](#gantt-chart)
7. [Pie Chart](#pie-chart)
8. [Mindmap](#mindmap)
9. [Timeline](#timeline)
10. [gitGraph](#gitgraph)
11. [Journey](#journey)

---

## Flowchart

```mermaid
flowchart TD
    A[Start] --> B{Decision}
    B -- Yes --> C[Action 1]
    B -- No --> D[Action 2]
    C --> E[End]
    D --> E
```

### Direction

- `flowchart TD` or `flowchart TB` — top-down (default)
- `flowchart LR` — left to right
- `flowchart BT` — bottom to top
- `flowchart RL` — right to left

### Node shapes

| Syntax | Shape |
|---|---|
| `id[Text]` | Rectangle (default) |
| `id(Text)` | Rounded rectangle |
| `id((Text))` | Circle |
| `id>Text]` | Flag (asymmetric) |
| `id{Text}` | Rhombus (decision) |
| `id[[Text]]` | Subroutine (double-rectangle) |
| `id[(Database)]` | Cylinder (database) |
| `id[/Text/]` | Parallelogram (input) |
| `id[\Text\]` | Parallelogram alt (output) |
| `id((Text))` | Circle |
| `id>Text]` | Asymmetric |
| `id{{Text}}` | Hexagon |
| `id[/Text\]` | Trapezoid alt |
| `id[\Text/]` | Trapezoid |
| `id(((Text)))` | Double circle |

### Edges

| Syntax | Meaning |
|---|---|
| `-->` | Solid arrow |
| `---` | Solid line (no arrow) |
| `===` | Thick line |
| `-.-` | Dotted line |
| `-.->` | Dotted arrow |
| `==>` | Thick arrow |
| `--x` | Arrow with X |
| `--o` | Circle arrow |
| `-- Edge text -->` | Labeled edge |
| `A -->|text| B` | Labeled edge (alt syntax) |
| `A -- text --> B` | Labeled edge (alt syntax) |

### Subgraphs

```mermaid
flowchart TB
    subgraph Frontend
        A[UI]
        B[State]
    end
    subgraph Backend
        C[API]
        D[DB]
    end
    A --> C
    C --> D
```

### Styling

```mermaid
flowchart LR
    A --> B --> C
    classDef green fill:#9f6,stroke:#333,stroke-width:2px;
    class A green;
    class B,C green;
    style A fill:#f9f,stroke:#333,stroke-width:4px;
```

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API
    participant DB
    U->>API: GET /resource
    activate API
    API->>DB: SELECT
    activate DB
    DB-->>API: rows
    deactivate DB
    API-->>U: 200 JSON
    deactivate API
    Note over U,API: HTTPS
```

### Participant types

- `participant Name` — basic
- `actor Name` — stick figure
- `participant Name as Alias` — with alias
- `box rgba(0,0,255,0.1) Title\n... end` — group participants

### Message types

- `->>` — solid line with arrowhead
- `-->>` — dotted line with arrowhead
- `--)` — dotted line with open arrow (async)
- `->` — solid line without arrowhead
- `--` — dotted line without arrowhead
- `-x` — solid line with X (rejected)

### Activations / Lifelines

- `activate A` / `deactivate A` — start/end a lifeline
- `A->>B+: msg` / `A->>B-: msg` — short syntax for activate/deactivate

### Notes

- `Note left of A: text` — note left of participant
- `Note right of A: text` — note right of participant
- `Note over A: text` — note over participant
- `Note over A,B: text` — note spanning multiple participants

### Loops / conditionals

```mermaid
sequenceDiagram
    loop Every minute
        A->>B: ping
        B-->>A: pong
    end
    alt Success
        B-->>A: ok
    else Failure
        B-->>A: err
    end
    opt Optional
        B->>C: log
    end
```

### Background highlights

- `rect rgb(200,220,255)\n... end` — colored background for a region

---

## Class Diagram

```mermaid
classDiagram
    class Animal {
        +String name
        +int age
        +makeSound() void
    }
    class Dog {
        +fetch() void
    }
    class Cat {
        +scratch() void
    }
    Animal <|-- Dog
    Animal <|-- Cat
    Dog "1" --> "*" Cat : chases
```

### Class members

- `+name: Type` — public
- `-name: Type` — private
- `#name: Type` — protected
- `~name: Type` — package private
- `+method(): ReturnType` — method
- `+method()* ReturnType` — abstract method
- `+method()$ ReturnType` — static method

### Relationships

- `<\|--` — inheritance
- `*--` — composition
- `o--` — aggregation
- `-->` — association
- `..>` — dependency
- `..|>` — realization
- `--` — solid link (no direction)

### Multiplicity

- `Animal "1" --> "*" Dog` — one to many
- `Animal "1" --> "1..*" Dog` — one to one-or-more
- `Animal "1" --> "0..1" Dog` — one to zero-or-one

### Generics

```mermaid
classDiagram
    class List~T~ {
        +items: T[]
        +add(T item)
    }
```

---

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Processing : start
    Processing --> Done : success
    Processing --> Failed : error
    Processing --> Idle : retry
    Done --> [*]
    Failed --> [*]
```

### Composite states

```mermaid
stateDiagram-v2
    [*] --> Active
    state Active {
        [*] --> Idle
        Idle --> Working
        Working --> Idle
    }
    Active --> [*]
```

### Transitions

- `A --> B : event` — labeled transition
- `A --> B : event / action()` — transition with action
- `A --> B : event [condition]` — guarded transition

### Notes

- `note left of A : text`
- `note right of A : text`
- `note left of A : text\nmulti-line`

### Fork / Join

```mermaid
stateDiagram-v2
    [*] --> Fork
    state Fork <<fork>>
    Fork --> State1
    Fork --> State2
    state Join <<join>>
    State1 --> Join
    State2 --> Join
    Join --> [*]
```

---

## ER Diagram

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    PRODUCT ||--o{ LINE_ITEM : "is in"

    USER {
        long id PK
        string name
        string email UK
    }
    ORDER {
        long id PK
        long user_id FK
        decimal total
    }
    LINE_ITEM {
        long id PK
        long order_id FK
        long product_id FK
        int quantity
    }
```

### Cardinality

- `||--||` — one to one
- `||--o{` — one to zero-or-more
- `||--|{` — one to one-or-more
- `}o--o{` — zero-or-more to zero-or-more
- `}|--|{` — one-or-more to one-or-more

### Attributes

- `long id PK` — primary key
- `long user_id FK` — foreign key
- `string email UK` — unique key
- `int age` — regular attribute

---

## Gantt Chart

```mermaid
gantt
    title Project Schedule
    dateFormat YYYY-MM-DD
    axisFormat %m/%d
    section Design
    Spec      :a, 2024-01-01, 7d
    Mockups   :after a, 5d
    section Dev
    Backend   :2024-01-15, 10d
    Frontend  :2024-01-20, 8d
    section Test
    QA        :2024-02-05, 5d
```

### Task syntax

- `Task name :id, start, duration`
- `Task name :id, after other, duration`
- `Task name :crit, id, start, duration` — critical task
- `Task name :done, id, start, duration` — completed task
- `Task name :active, id, start, duration` — in-progress task

### Section

- `section Section Name` — groups tasks

### Milestones

- `Milestone :milestone, id, date, 0d`

### Excluding weekends

- `excludes weekends`
- `excludes monday,friday`

---

## Pie Chart

```mermaid
pie title Browser Market Share
    "Chrome" : 65
    "Safari" : 18
    "Firefox" : 5
    "Edge" : 4
    "Other" : 8
```

### Theme

```mermaid
pie showData
    title ...
    "A" : 30
    "B" : 70
```

- `showData` — show numeric values
- `title` — chart title (one line)

---

## Mindmap

```mermaid
mindmap
  root((Project))
    Frontend
      React
      Tailwind
    Backend
      FastAPI
      PostgreSQL
    DevOps
      Docker
      CI/CD
```

### Node shapes

- `id` — plain text
- `id[Text]` — square
- `id(Text)` — rounded
- `id((Text))` — circle
- `id{{Text}}` — bang (hexagon)
- `id)Text(` — cloud
- `id))Text((` — burst

### Icons

- `id["Text\n🚀"]` — with emoji
- Use Font Awesome via `fa:fa-icon-name` syntax (when supported)

---

## Timeline

```mermaid
timeline
    title Project History
    section 2022
      Q1 : Idea
      Q4 : Prototype
    section 2023
      Q1 : MVP
      Q3 : v1.0
    section 2024
      Q2 : Scale
```

### Time period

- `2024 : event` — year
- `2024-Q1 : event` — quarter
- `2024-03 : event` — month
- `2024-03-15 : event` — date

### Multi-event per period

- `2024 : event 1 : event 2 : event 3`

---

## gitGraph

```mermaid
gitGraph
    commit id: "init"
    commit id: "feat-A"
    branch develop
    checkout develop
    commit id: "dev-1"
    branch feature/x
    checkout feature/x
    commit id: "WIP"
    checkout develop
    merge feature/x
    checkout main
    merge develop
    commit id: "release" tag: "v1.0"
```

### Keywords

- `commit` — add a commit on current branch
- `branch Name` — create new branch
- `checkout Name` — switch to branch
- `merge Name` — merge branch into current
- `cherry-pick id: "abc123"` — cherry-pick a commit

### Commit options

- `commit id: "abc123"`
- `commit tag: "v1.0"`
- `commit type: HIGHLIGHT` — highlight commit
- `commit type: NORMAL` — normal (default)

### Horizontal vs vertical

- `gitGraph LR:` — left-right (default horizontal)
- `gitGraph BT:` — bottom-top (vertical)

---

## Journey

```mermaid
journey
    title User shopping journey
    section Browse
      Visit homepage: 5: User
      Search product: 4: User
    section Buy
      Add to cart: 5: User
      Checkout: 3: User, System
      Pay: 2: User
    section After
      Receive email: 5: User, System
```

### Task line

- `Task name: score: actor1, actor2`

- `score` — 1 (low) to 5 (high), how the user feels
- `actor` — comma-separated list of participants

### Sections

- `section Section Name` — groups tasks

---

## Common Configuration

### Frontmatter (theme, look, etc.)

```mermaid
---
config:
  theme: base
  look: handDrawn
---
flowchart LR
    A --> B
```

Themes: `default`, `base`, `dark`, `forest`, `neutral`, `null`
Looks: `classic` (default), `handDrawn`, `rect`
