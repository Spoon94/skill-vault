# Class Diagram Example

A class diagram for a simple e-commerce domain.

```mermaid
classDiagram
    class User {
        +Long id
        +String name
        +String email
        +login(password: String) boolean
        +logout() void
    }

    class Order {
        +Long id
        +Date createdAt
        +Decimal total
        +addItem(p: Product, qty: int) void
        +checkout() void
    }

    class OrderItem {
        +Long id
        +int quantity
        +Decimal unitPrice
    }

    class Product {
        +Long id
        +String name
        +Decimal price
        +int stock
    }

    class Category {
        +Long id
        +String name
    }

    User "1" -- "*" Order : places
    Order "1" -- "*" OrderItem : contains
    OrderItem "*" -- "1" Product : refers to
    Product "*" -- "*" Category : tagged with
    Product <|-- DigitalProduct
    Product <|-- PhysicalProduct

    class DigitalProduct {
        +String downloadUrl
        +download() void
    }

    class PhysicalProduct {
        +Double weight
        +String warehouseLocation
    }
```

## Key syntax

- `class Name {\n  +member\n  +method()\n}` — class with members
- `+` public, `-` private, `#` protected, `~` package private
- `<\|--` — inheritance
- `*--` — composition (filled diamond)
- `o--` — aggregation (empty diamond)
- `-->` — association
- `..>` — dependency
- `"1" -- "*"` — multiplicity labels
- `: rel label` — relationship label

## Common variations

- `class List~T~` — generic class
- `<<interface>>` / `<<abstract>>` stereotypes
- `+method()* ReturnType` — abstract method
- `+method()$ ReturnType` — static method
