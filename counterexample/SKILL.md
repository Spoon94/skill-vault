---
name: counterexample
description: Force a concrete counterexample or falsification case into an artifact, explanation, plan, design, claim, or mental model before it is trusted. Use to stress-test a polished output that might be selling a wrong model, when the user asks for a counterexample / edge case / "where does this break" / falsification, or as a follow-on check after any explanation, explainer, design, or plan is produced.
---

# counterexample — Force a Falsification Block

The trap of a polished artifact is that it can **sell a wrong mental model with confidence**. A beautiful explanation, diagram, plan, or design reads as correct precisely because it is polished. Before any such output is trusted, force in at least one concrete case where the model **breaks**.

This skill has no opinion about content. It only enforces one thing: **the output must contain an explicit counterexample / failure case**, or state — with evidence — why no realistic one exists.

## When to invoke

- After any explanation, explainer, diagram, plan, design, or claim is produced — run this as a check before presenting or acting on it.
- When the user asks for a counterexample, edge case, falsification, "where does this break", "when is this wrong", or "stress-test this".
- When an output reads suspiciously smooth, complete, or happy-path-only.

## What to produce

For the given artifact or claim, output a **counterexample block** with these parts:

1. **The model as stated** — one sentence: what the artifact / claim currently asserts.
2. **A concrete counterexample** — a specific, named case (input, input shape, environment, ordering, boundary value, adversarial example) where that assertion fails. Not "sometimes it breaks" — a concrete instance you can state exactly.
3. **Why it breaks** — the mechanism: which assumption in the model the counterexample violates.
4. **What it reveals** — the corrected or tightened claim: what is now true, and the boundary of where the model actually holds.
5. **Falsification test** — a check the user can run to see the failure (a command, a query, a small experiment).

If, after genuine effort, no realistic counterexample exists, say so **and show the reasoning you used to search** (what you tried, what edge cases you probed). Never declare "no counterexample" without showing the search.

## Placement

Append the counterexample block **to the same artifact** if you produced it — do not leave it as a separate, easily-skipped aside. If you are reviewing someone else's output, present the block immediately after quoting the claim it targets.

## Hard rules

- **Concrete, not rhetorical.** "An attacker could send a malformed payload" is not a counterexample. "Sending `POST /upload` with `Content-Length: 0` causes the server to hang" is.
- **Mechanism, not just instance.** State *why* it breaks, not only *that* it breaks.
- **Boundary, not demolition.** The point is not to destroy the model but to find where it stops being true — so the corrected claim is stronger.
- **No weakening.** Do not soften a real failure into a footnote, caveat, or "rare edge case" if it is realistic and within scope.
- **One deep counterexample beats five shallow ones.** Prefer the single most instructive break over a scattershot list.

## Optional: hook mode

When asked to run as a **follow-on hook** after another skill's output (an explainer, a diagram, a plan, a design), take that output as input and do only the counterexample block above — do not regenerate the explanation. State at the top: "Counterexample check on the [type of artifact] above."

## Output contract

```markdown
## Counterexample

**Model as stated:** <one sentence>
**Counterexample:** <concrete case>
**Why it breaks:** <mechanism / violated assumption>
**What it reveals:** <corrected / bounded claim>
**Falsification test:** <how to observe the failure>
```

—or, when none exists:

```markdown
## Counterexample — none found (with search)

**Searched:** <what edge cases / inputs / boundaries were probed>
**Why the model held:** <reasoning>
**Confidence caveat:** <what would change this answer>
```
