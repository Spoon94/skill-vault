---
name: ste
description: Rewrite deliverable English into ASD-STE100 Simplified Technical English — one meaning per word, active voice, simple tense, short sentences, one instruction per sentence. Use when asked to apply STE / STE100 / controlled English, simplify agent output, reduce ambiguity, or make text safe for downstream agents, translation, or non-native readers.
---

# ste — ASD-STE100 Controlled-English Rewriting

Rewrite the **final deliverable text** into ASD-STE100 Simplified Technical English. The rules apply **only to the output layer** — never let them leak into your reasoning, analysis, or drafting.

> **Hard rule — constraint placement.** Do all your thinking, exploring, and drafting in normal full English first. Apply STE **only as the last transformation**, right before presenting text the user will consume or hand to another agent. Do not "write simply while you think" — enforced at the thought level it measurably degrades reasoning quality. Think freely, then constrain the surface.

## Scope

Use STE when the text will be **parsed by a machine or a non-native reader with no human to ask a follow-up question**:

- Agent-to-agent messages, tool / function descriptions, error messages, system prompts
- Instructions handed to another agent, a translation pipeline, or a downstream system
- Any output where a misread carries real cost

**Do not use STE** for creative writing, marketing copy, persuasive text, or anything where voice and nuance are the point. STE is deliberately flat and literal.

## Optional intensity: `--level` / `~80%`

By default apply the rules fully. If the user asks for a softer pass ("80% of the way", "loosely STE"), apply the word-choice and voice rules but relax the hard length caps — keep ambiguity removed, keep meaning exact, stop short of the strictest form. Always state which level you applied.

## Rewrite rules

| Rule | Do | Don't |
|---|---|---|
| One word, one meaning | Pick one verb for one action and reuse it every time | Rotate synonyms for the same idea |
| One part of speech per word | Use a word only in its approved role | "Oil the valve" when "oil" is a noun only |
| Active voice | "The agent deletes the file." | "The file is deleted." (unless the actor is unknown) |
| Simple tenses only | "We received the report." | "We have received the report." |
| One instruction per sentence | "Open the file. Read line 3." | "Open the file and read line 3, then check." |
| Sentence length | ≤20 words instructions, ≤25 words descriptions | Long compound / subordinate sentences |
| Noun clusters | ≤3 words | 4+ word noun stacks |
| No ellipsis | Keep subject, verb, article explicit | Drop words to save space |
| Paragraph limits | One topic per paragraph, ≤6 sentences | Multi-topic paragraphs |
| Lists for sequences | Numbered/bulleted list for 3+ steps | Bury a sequence in one prose sentence |

Common replacements: `prior to`→`before`, `utilize`→`use`, `commence`→`start`, `ensure`→`make sure`, `replenish`→`fill`, `approximately`→`about`, `in order to`→`to`.

## Process

1. Read the input once for meaning. Do not rewrite before you understand what it must still say.
2. Flag every violation sentence by sentence.
3. Rewrite each flagged sentence, **preserving every fact, condition, exception, scope qualifier, and number exactly**. If a shorter phrasing would drop required precision (a safety condition, a scope limit), keep the longer phrasing and flag the trade-off — never silently simplify.
4. Produce the before/after table.
5. If the input already complies, say so. Do not force changes onto compliant text.

## Output contract

Return:

1. The **rewritten text** (STE-applied).
2. A **before/after table** of changed sentences:

```markdown
| Rule violated | Original | Rewritten |
|---|---|---|
| Present perfect tense | "We have received your request." | "We received your request." |
| Noun cluster (4+ words) | "the agent task queue priority handler" | "the handler that sets task-queue priority" |
```

3. A short **left-unsimplified** note for anything deliberately kept long (and why).

## References

- `references/writing-rules.md` — paraphrased rule summary and sources (from `kv0906/cc-skills/asd-ste100`, MIT)
- `examples/before-after.md` — official-rule illustrations + agent-output examples
- Official standard (free download): https://www.asd-ste100.org/

This skill applies the *principle* (plainest available word, used the same way every time) rather than checking against ASD's ~900-word approved dictionary. For certified STE-compliant documentation, check word-by-word against the real dictionary.
