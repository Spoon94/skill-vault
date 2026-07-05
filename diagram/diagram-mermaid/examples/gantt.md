# Gantt Chart Example

A project schedule with multiple sections, dependencies, and milestones.

```mermaid
gantt
    title Product Launch Q1 2025
    dateFormat YYYY-MM-DD
    axisFormat %m/%d

    section Discovery
    User research    :a1, 2025-01-06, 7d
    Stakeholder ints :a2, after a1, 5d
    Spec writing     :a3, after a2, 3d
    Spec sign-off    :milestone, m1, after a3, 0d

    section Design
    Wireframes       :d1, after m1, 4d
    Visual design    :d2, after d1, 5d
    Design review    :d3, after d2, 2d

    section Dev
    Backend API      :b1, after d3, 10d
    Frontend impl    :b2, after d3, 8d
    Integration      :b3, after b1, 5d
    Code freeze      :milestone, m2, after b3, 0d

    section QA
    Test cases       :t1, after b2, 3d
    QA testing       :t2, after m2, 5d
    Bug fix          :t3, after t2, 3d
    Release          :milestone, m3, after t3, 0d
```

## Key syntax

- `gantt` — diagram type keyword
- `title` — chart title
- `dateFormat YYYY-MM-DD` — input date format
- `axisFormat %m/%d` — display date format
- `section Section Name` — group tasks
- `Task name :id, start, duration` — basic task
- `Task name :id, after other, duration` — dependent task
- `Task name :crit, id, start, duration` — critical (red)
- `Task name :done, id, ...` — completed
- `Task name :active, id, ...` — in-progress
- `Milestone name :milestone, id, date, 0d` — milestone (zero duration)

## Common variations

- `excludes weekends` — skip weekends
- `excludes friday` — skip specific weekdays
- `todayMarker off` — hide today line
- Multiple sections in one chart
