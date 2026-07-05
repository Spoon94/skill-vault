# ER Diagram Example

An entity-relationship diagram for a blog system.

```mermaid
erDiagram
    USER ||--o{ POST : writes
    POST ||--|{ COMMENT : has
    POST }o--o{ TAG : tagged with
    USER ||--o{ COMMENT : authors
    CATEGORY ||--o{ POST : contains

    USER {
        long id PK
        string name
        string email UK
        timestamp created_at
    }

    POST {
        long id PK
        long author_id FK
        long category_id FK
        string title
        text body
        timestamp published_at
    }

    COMMENT {
        long id PK
        long post_id FK
        long author_id FK
        text content
        timestamp created_at
    }

    TAG {
        long id PK
        string name UK
    }

    CATEGORY {
        long id PK
        string name
    }
```

## Key syntax

- `A ||--o{ B : rel_label` — one to zero-or-more
- `||--||` — one to one
- `||--|{` — one to one-or-more
- `}o--o{` — zero-or-more to zero-or-more
- `}|--|{` — one-or-more to one-or-more

## Attribute keys

- `PK` — primary key
- `FK` — foreign key
- `UK` — unique key
- (no suffix) — regular attribute

## Common variations

- `A ||--o{ B : "is in"` — quoted relationship label
- Attribute type can be any string: `long`, `string`, `text`, `timestamp`, `decimal`, etc.
