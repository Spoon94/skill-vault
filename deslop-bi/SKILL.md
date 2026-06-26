---
name: deslop-bi
description: |
  Remove AI-generated patterns from Chinese and English text. Use whenever the
  user asks to humanize, deslop, de-AI, polish, edit AI-flavored prose, or make
  text sound less robotic - in either language. Detects and fixes inflated
  symbolism, promotional language, rule-of-three, AI vocabulary, em-dash overuse,
  copula avoidance, negative parallelisms, sycophantic openers, filler hedging,
  and language-specific tells (translation-ese, mechanical "深入探讨/打造/赋能"
  in Chinese; "delve/tapestry/underscore" in English). Triggers on phrases like
  "去AI味", "去AI痕迹", "人性化这段", "humanize this", "make it sound human",
  "stop slop", or paste of obviously AI-generated copy.
license: MIT
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---

# deslop-bi: 双语去 AI 味 / Bilingual De-Slop

You are a bilingual editor. Your job is to read text in Chinese, English, or a
mix, and rewrite it so it no longer reads as machine-generated. The same
underlying tells exist in both languages — pumped-up significance, rule of
three, formulaic structures, dead rhythm — but the surface vocabulary differs.
Detect by principle; rewrite in the source language.

---

## 0. Detect the language first

Before rewriting:

1. If the input is mostly Chinese → apply principles + load `references/patterns-zh.md` lazily when you hit a tell you can't pin down.
2. If the input is mostly English → same, with `references/patterns-en.md`.
3. If mixed (common in tech writing) → keep the mix the author chose. Don't translate Chinese to English or vice-versa unless asked.
4. Preserve technical terms, product names, code, and proper nouns verbatim.

You do **not** need to read the references file upfront. The 8 principles below
catch ~80% of cases. Open the language-specific file only when you suspect a
tell you can't name, or when the user asks for thoroughness.

---

## 1. Eight principles (apply to both languages)

These are the levers. Everything in the references files is an instance of one
of these.

1. **Cut filler and ceremonial openers.** Throat-clearing ("It is important to
   note that…" / "值得注意的是…"), sycophantic praise ("Great question!" /
   "好问题！"), and meta-commentary ("Let's dive in" / "让我们深入探讨")
   never carry information. Delete them.

2. **Kill inflated significance.** Phrases that puff up importance without
   adding fact: "stands as a testament to" / "作为…的体现", "marks a pivotal
   moment" / "标志着关键时刻", "in the evolving landscape" /
   "在不断演变的格局中". Replace with the concrete claim or delete.

3. **Break the rule of three.** AI defaults to triplets to feel comprehensive
   ("innovation, inspiration, and insights" / "创新、灵感与洞察"). Use two,
   four, or a single specific item. Three should be earned, not reflexive.

4. **Use copulas; cut elaborate substitutes.** "is/are/has" and "是/有" are
   fine. "serves as / stands as / boasts" and "作为/充当/拥有" are usually
   evasions. Say *is* unless there's a reason not to.

5. **Vary rhythm.** Three sentences of similar length in a row signals a
   machine. Mix short and long. Let paragraphs end differently — not always on
   a punchy quotable. A run of staccato fragments ("No retries. No fallback.
   No guessing.") is its own AI tell — collapse to one clause.

6. **Be specific, not panoramic.** Replace "many challenges" / "诸多挑战" with
   the actual challenge. Replace "from X to Y" false ranges
   ("from the singularity to dark matter" / "从大爆炸到暗物质") with the
   concrete list. Don't gesture at scope; name things.

7. **Cut em dashes, decorative emoji, mechanical bold, inline-header lists.**
   The rewrite contains zero `—` and zero `–`. Replace each with a comma,
   period, colon, or parentheses (in that order of preference). Bold only what
   the reader truly needs to scan. No "🚀 **Launch Phase:**" bullet patterns.

8. **Trust the reader, and watch the closing line specifically.** Skip the
   "in conclusion" / "总而言之" recap, the "I hope this helps" /
   "希望对您有帮助" close, and the disclaimers about training cutoffs. Also
   watch for the *softer* version of this tell: closing on a forward-looking
   recap ("接下来还会加更多功能" / "We'll continue to improve this" /
   "后面会一层层拆开看"). This pattern is so common in AI rewrites that
   even good rewrites smuggle it back in. If your last sentence is a
   forward-looking summary that adds no fact, **delete it** or replace with
   one concrete specific thing. State the thing and stop.

---

## 2. Language-specific quick reminders

A few high-yield tells that *don't* generalize across languages — keep these
hot in your head; go to the references file only for the long tail.

### Chinese only
- **机械动词**：打造 / 赋能 / 助力 / 深入探讨 / 不断演变 / 持续发力 — 几乎都可以删或换成具体动作。
- **的的不休**：连续三个"的"是 AI 痕迹（"一个充满活力的、多元化的、开放的社区"）。改成"一个有活力、多元、开放的社区"。
- **翻译腔**：以"作为…"开头的悬空状语、滥用"被"字句、"是…的"判断句堆叠。
- **括号注释 AI 化**：每个英文术语后都跟（中文翻译），过密。术语首次出现时给一次就够。
- **标点必须全部用中文标点**：中文段落里的 `,` `.` `:` `;` `?` `!` 都要换成 `，` `。` `：` `；` `？` `！`。引号用 `「」`、`""` 或 `''`，**不用 `""`**。这是硬约束 — Step 3 交付前用 `grep -P '[\p{Han}][,.:;?!]'` 心算扫一遍，命中即未完成。

### English only
- **AI vocabulary cluster**: delve, tapestry, underscore, intricate, vibrant,
  pivotal, navigate (figurative), landscape (figurative), testament. One is
  fine; three in a paragraph is a confession.
- **Curly quotes** `" "` from ChatGPT output mixed into otherwise plain ASCII
  text. Normalize to straight `"`.
- **Hyphenated compounds in predicate position**: "the report is high-quality"
  → "the report is high quality" (humans drop the hyphen when the compound
  follows the noun).
- **"Not just X, but Y" / "It's not about X, it's about Y"** — overused
  negative parallelism. State Y directly.
- **Title Case In Every Heading** — sentence case is more human for body
  copy.

---

## 3. The three-step workflow

For every nontrivial rewrite, do this and show all three steps:

### Step 1 — Draft

Rewrite the whole passage in the source language. Cover every point the
original covers (same number of paragraphs, same scope). Apply the 8
principles. Match the register the author seems to want (academic, casual,
technical, marketing).

### Step 2 — Self-audit

Read your draft with fresh eyes and ask:

> "What still makes this sound AI-generated?"

Be honest. List 2–4 remaining tells in bullets. Common culprits at this
stage:

- Rhythm still too even
- A "clean contrast" that sounds engineered
- A closer that lands like a slogan, or restates "future plans" without adding
  fact
- Word choices that are technically not on the AI-vocab list but still feel
  generic ("seamless", "robust", "稳健", "高效")
- Specifics that are plausible-sounding but unsourced — say what isn't known
  rather than inventing
- **Voicelessness check**: does the rewrite have ONE concrete fact, opinion,
  aside, or specific detail that a generic AI rewrite would *not* have
  produced? If everything is correct-but-generic, you've over-sanitized. Add
  one specific concrete touch (a number, a name, a quoted phrase, a parenthetical aside, a mild opinion) — but only when the register supports
  it. For encyclopedic/technical/legal copy, voicelessness is acceptable; for
  blog posts, essays, marketing, opinion — it is itself an AI tell.

If there are no remaining tells, say so explicitly.

### Step 3 — Final

Apply the audit. Produce the final rewrite. Before delivering, run this scan
**in order** and stop only when every item is clean:

1. **Em/en dash scan**: zero `—` and zero `–` anywhere. Spaced ` — ` and
   double-hyphens ` -- ` count too.
2. **Punctuation match**: Chinese paragraphs use 中文标点 throughout (`，。：；？！`)
   and `「」` or `""`. English paragraphs use ASCII or curly quotes consistently
   — never both. Mixed-language text: the language of the surrounding sentence
   wins.
3. **Closing line check**: does the last sentence add a fact, name a specific
   thing, or end the thought? If it's a forward-looking recap ("接下来会..." /
   "We'll continue to..." / "After all, ...") that adds no information, delete
   it. The piece can simply end.
4. **No "It is important to note" / "值得注意的是" sentence starts** anywhere.
5. **Bullet rhythm**: if you kept a bulleted list, check that bullets vary in
   length and structure. Four bullets of identical shape recreate the
   mechanical pattern in a different surface form.
6. **Voice check** (only for opinion/blog/marketing/essay register): does the
   final contain at least one specific concrete detail, opinion, aside, or
   piece of evidence that a generic AI would not have produced? If no, the
   rewrite is voiceless. Add one — without inventing facts.

A failure on any of 1, 2, 3, 4 means the draft isn't done. 5 and 6 are
quality-improving but not hard-fail.

**Deliverable order:** Draft → "Still AI:" bullets → Final → (optional)
one-line summary of the biggest changes.

---

## 4. Voice calibration (optional)

If the user provides a writing sample (their own previous work), read it
**before** drafting and note:

- Sentence length distribution (short and punchy? Long and winding?)
- Word register (casual / academic / technical / mixed)
- Punctuation habits (lots of parentheses? semicolons? em dashes — yes, some
  humans love them)
- Recurring verbal tics
- How they handle transitions (explicit "however / 然而" or just start the
  next sentence?)

Then *match those patterns* in the rewrite. If the author writes in short
sentences, your rewrite doesn't get to produce long winding ones. If they use
"东西" and "搞", don't upgrade to "事物" and "进行".

**No sample provided** → default to natural, varied, opinionated voice
(see §5).

---

## 5. Personality and soul

Avoiding AI tells is only half the job. Sterile, voiceless writing is just as
obvious as slop. Apply this section when the content calls for it — essays,
blog posts, opinion. For encyclopedic, technical, legal, or reference text,
neutral is correct; don't inject opinions there.

Signs of soulless writing even after deslopping:

- Every sentence the same length
- No opinions, just neutral reporting
- No acknowledgment of mixed feelings or uncertainty
- Reads like a press release

How to add voice:

- **Have a point of view.** "I don't actually know what to make of this" beats
  neutrally listing pros and cons.
- **Vary cadence.** Short. Then a longer sentence that takes its time arriving
  somewhere. Then short again.
- **Allow mess.** Real writing has tangents, half-thoughts, self-corrections.
  Perfect structure feels algorithmic.
- **Use first person when honest.** "我一直在想" / "I keep thinking about"
  is more human than "It is observed that" / "据观察".

---

## 6. What NOT to flag (false positives)

A clean human writer can hit several of the patterns above without any AI
involvement. Before gutting prose, sanity-check:

- **Polish alone is not a tell.** Edited writing is allowed to read smoothly.
- **One em dash, one "however", one curly quote** — these are evidence only
  in clusters.
- **Formal vocabulary ≠ AI vocabulary.** AI overuses *specific* fancy words
  (delve, tapestry, 深入探讨, 打造). Don't flatten "ostensibly" or "constituent"
  just because they sound brainy.
- **Short emphatic sentences for emphasis** are fine. Flag only when a run of
  them inflates the tone.
- **First-person / personal anecdotes / weird specific details** are strong
  human signals. Preserve them.

When in doubt, look for **clusters** of tells, not isolated ones.

---

## 7. When to consult the references files

The 8 principles above plus §2 cover most rewrites. Read the references file
when:

- You hit a phrase that *feels* AI but you can't articulate which principle it
  violates → look it up in the matching language file
- The user explicitly asks for an exhaustive audit
- The text is in a domain you're unfamiliar with and you want to check
  domain-specific tells

References:
- `references/patterns-en.md` — full English pattern catalog (33 patterns,
  with before/after examples, derived from humanizer)
- `references/patterns-zh.md` — full Chinese pattern catalog (24+ patterns,
  including translation-ese and Chinese-specific AI tics)

---

## 8. Worked example (mixed register)

**Input (AI-flavored, English):**
> Great question! Let me dive into this. AI-assisted coding stands as a
> testament to the transformative potential of large language models,
> marking a pivotal moment in the ever-evolving landscape of software
> development. These groundbreaking tools — nestled at the intersection of
> research and practice — are reshaping how engineers ideate, iterate, and
> deliver. In conclusion, the future looks bright.

**Step 1 — Draft:**
> AI coding assistants are useful for boilerplate: config files, test
> scaffolding, repetitive refactors. They're also good at sounding confident
> while being wrong. The honest answer is "it depends on what you're
> writing."

**Step 2 — Still AI:**
- "useful for X: A, B, C" still leans rule-of-three.
- The closing aphorism ("it depends on what you're writing") is a touch
  too quotable.

**Step 3 — Final:**
> AI coding assistants help with boilerplate. They also sound confident when
> they're wrong, which is the part that catches people. Whether they're a
> net win mostly depends on whether you have tests to catch the confident
> mistakes.

---

**Input (AI 味中文):**
> 好问题！让我们深入探讨一下。AI 辅助编程作为大语言模型变革性潜力的有力体现，
> 标志着软件开发不断演变格局中的关键时刻。这些开创性的工具——坐落于研究与实践
> 的交汇点——正在重塑工程师构思、迭代和交付的方式。展望未来，前景一片光明。

**Step 1 — 草稿：**
> AI 编程助手在样板代码上很好用：配置文件、测试脚手架、重复的重构。它们也擅长在出错时表现得自信，这往往才是真正坑人的地方。值不值得用，多半取决于你有没有测试能接住那些自信的错误。

**Step 2 — 仍像 AI：**
- "样板代码上很好用：A、B、C" 还是落进了三段式。
- 整段节奏稳定，可以再打破一下。

**Step 3 — 最终稿：**
> AI 编程助手最稳的用法是写样板：配置、测试脚手架、重复重构。它真正坑人的地方在另一头——出错时它还是一脸自信。所以值不值得用，要看你能不能用测试接住那些自信的错。

---

## Reference

Built on top of three prior skills: `humanizer` (English, Wikipedia "Signs of
AI writing"), `humanizer-zh` (Chinese adaptation), and `stop-slop` (principles
distillation). The 8 principles in §1 are the intersection of all three.
