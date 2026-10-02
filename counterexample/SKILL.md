---
name: counterexample
description: Force a concrete counterexample or falsification case into an artifact, explanation, plan, design, claim, or mental model before it is trusted. Use to stress-test a polished output that might be selling a wrong model, when the user asks for a counterexample / edge case / "where does this break" / falsification, or when the user asks to run a falsification check on a just-produced artifact.
license: MIT
allowed-tools: Read, Grep, Glob
metadata:
  origin: self-created
---

# counterexample — Force a Falsification Block

The trap of a polished artifact is that it can **sell a wrong mental model with confidence**. A beautiful explanation, diagram, plan, or design reads as correct precisely because it is polished. Before any such output is trusted, force in at least one concrete case where the model **breaks**.

This skill has no opinion about content. It only enforces one thing: **the output must contain an explicit counterexample / failure case**, or state — with evidence — why no realistic one exists.

## When to invoke

- After any explanation, explainer, diagram, plan, design, or claim is produced — run this as a check before presenting or acting on it.
- When the user asks for a counterexample, edge case, falsification, "where does this break", "when is this wrong", or "stress-test this".
- When an output reads suspiciously smooth, complete, or happy-path-only.

Target artifact or claim: $ARGUMENTS — 若无参数，检查当前对话中最近产出的产物。

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
- **No fabricated cases.** A counterexample must come from actually running the falsification test yourself when feasible, or from an explicit, checkable reasoning chain (cite the exact code path / input / state that produces the failure). If you cannot ground it either way, you MUST use the "Counterexample — none found (with search)" branch instead of inventing one. 反例必须来自实跑或可复现推理链；两者都做不到时走 none-found 分支，禁止编造。

## Optional: hook mode

There is no mechanism that automatically runs one skill as a hook after another skill's output — never enter hook mode just because an artifact was produced. Hook mode applies only when the user explicitly asks for it (「对上面这个方案做反例检查」, "counterexample check", 「给这个讲解挑反例」). Take the referenced output as input and do only the counterexample block above — do not regenerate the explanation. State at the top: "Counterexample check on the [type of artifact] above."

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
