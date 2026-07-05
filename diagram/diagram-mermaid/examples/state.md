# State Diagram Example

A state machine for an order lifecycle, including retry and terminal states.

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Paid : payment received
    Pending --> Cancelled : user cancels
    Paid --> Processing : merchant accepts
    Processing --> Shipped : items packed
    Processing --> Failed : out of stock
    Failed --> Pending : restock
    Shipped --> Delivered : carrier delivers
    Delivered --> Returned : user returns
    Returned --> [*]
    Delivered --> [*]
    Cancelled --> [*]

    state Processing {
        [*] --> ReserveStock
        ReserveStock --> PackItems : reserved
        PackItems --> AssignCarrier : packed
        AssignCarrier --> [*] : ready
    }

    note left of Failed : auto-retry 3x then notify
    note right of Shipped : tracking email sent
```

## Key syntax

- `stateDiagram-v2` — modern syntax (use this, not `stateDiagram`)
- `[*]` — initial/final pseudo-state
- `A --> B : event` — labeled transition
- `state Name {\n  ...\n}` — composite state
- `note left of X : text` — note attached to state

## Common variations

- `A --> B : event [condition]` — guarded transition
- `A --> B : event / action()` — transition with action
- `state Fork <<fork>>` — fork pseudo-state
- `state Join <<join>>` — join pseudo-state
- `note left of A : text\nmulti-line`
