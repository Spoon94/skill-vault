# Timeline Example

A timeline showing project milestones over multiple years.

```mermaid
timeline
    title Anthropic Timeline
    section 2021
      Q1 : Anthropic founded
      Q4 : First Claude model
    section 2022
      Q2 : Constitutional AI paper
      Q4 : Claude 1 released
    section 2023
      Q1 : Claude 2 with 100k context
      Q3 : Claude 2.1
    section 2024
      Q1 : Claude 3 family (Haiku/Sonnet/Opus)
      Q3 : Claude 3.5 Sonnet
      Q4 : Claude 3.5 Sonnet v2 + computer use
    section 2025
      Q2 : Claude 4 (Opus 4 / Sonnet 4)
      Q3 : Claude 4.5 / 4.6 / 4.7
```

## Key syntax

- `timeline` — diagram type keyword
- `title ...` — chart title
- `section Year` — group events by year/era
- `Period : event` — single event in a period
- `Period : event1 : event2 : event3` — multiple events (colon-separated)

## Time period formats

- `2024` — year
- `2024-Q1` — quarter
- `2024-03` — month
- `2024-03-15` — date
- `Week 5` — custom period

## Common variations

- Multiple sections per timeline
- Multi-event periods with `:` separator
- Mix of year/quarter/month periods in same timeline
