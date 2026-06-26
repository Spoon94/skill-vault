# English AI patterns — full catalog

Open this file when SKILL.md's 8 principles don't fully name what's wrong with
a passage, or when the user asks for an exhaustive audit. Patterns derived
from Wikipedia's "Signs of AI writing" (WikiProject AI Cleanup).

## Contents

- Content tells (§1–6)
- Language & grammar tells (§7–13)
- Style & formatting tells (§14–19)
- Communication artifact tells (§20–22)
- Filler, hedging, and rhetorical tells (§23–33)

---

## Content tells

### 1. Inflated significance / legacy / "broader trends"

Watch: *stands as / serves as, is a testament to, marks a pivotal moment, plays
a crucial role, underscores its importance, reflects a broader, symbolizing
its enduring, contributing to the, setting the stage for, key turning point,
evolving landscape, focal point, indelible mark, deeply rooted.*

Before: The Statistical Institute of Catalonia was officially established in
1989, marking a pivotal moment in the evolution of regional statistics in
Spain.
After: The Statistical Institute of Catalonia was established in 1989 to
collect regional statistics independently of Spain's national office.

### 2. Inflated notability / media coverage

Watch: *independent coverage, national media outlets, written by a leading
expert, active social media presence.*

Before: Her views have been cited in The New York Times, BBC, Financial Times,
and The Hindu. She maintains an active social media presence with 500,000
followers.
After: In a 2024 New York Times interview she argued AI regulation should
focus on outcomes rather than methods.

### 3. Superficial `-ing` analysis

Watch sentence-end participles that pretend to add depth: *highlighting…,
ensuring…, reflecting…, contributing to…, fostering…, showcasing….*

Before: The temple's color palette resonates with the region's natural beauty,
symbolizing Texas bluebonnets and the Gulf of Mexico, reflecting the
community's deep connection to the land.
After: The temple uses blue, green, and gold. The architect chose them to
reference bluebonnets and the Gulf coast.

### 4. Promotional / brochure language

Watch: *boasts, vibrant, rich (figurative), nestled, in the heart of,
breathtaking, must-visit, renowned, stunning, groundbreaking, exemplifies,
commitment to.*

Before: Nestled within the breathtaking region of Gonder, Alamata Raya Kobo
stands as a vibrant town with a rich cultural heritage.
After: Alamata Raya Kobo is a town in the Gonder region of Ethiopia, known
for its weekly market and 18th-century church.

### 5. Vague attribution / weasel sources

Watch: *industry reports, observers have cited, experts argue, some critics
argue, several sources.*

Before: Experts believe the Haolai River plays a crucial role in the regional
ecosystem.
After: The Haolai River supports several endemic fish species (Chinese
Academy of Sciences survey, 2019).

### 6. Formulaic "Challenges and future prospects" sections

Watch: *Despite its… faces challenges…, Despite these challenges, Future
Outlook, Legacy.*

Before: Despite its industrial prosperity, Korattur faces challenges typical
of urban areas… Despite these challenges, with its strategic location,
Korattur continues to thrive.
After: Traffic congestion increased after 2015 when three IT parks opened.
A stormwater drainage project began in 2022.

---

## Language & grammar tells

### 7. AI vocabulary cluster

High-frequency post-2023 words that co-occur: *delve, tapestry, underscore,
intricate, intricacies, pivotal, vibrant, robust, seamless, navigate
(figurative), landscape (figurative), testament, foster, garner, align with,
crucial, key (adjective), enduring, valuable, showcase.* One is fine; three
in a paragraph is a confession.

### 8. Copula avoidance

Watch: *serves as / stands as / marks / represents / boasts / features /
offers a…*

Before: Gallery 825 serves as LAAA's exhibition space and boasts over 3,000
square feet.
After: Gallery 825 is LAAA's exhibition space. It has 3,000 square feet.

### 9. Negative parallelism / tailing negation

Watch: "Not only X but Y", "It's not just X, it's Y", and clipped negative
fragments tacked on the end ("no guessing", "no wasted motion").

Before: It's not just about the beat under the vocals; it's about the
aggression. It's not merely a song, it's a statement.
After: The heavy beat adds to the aggressive tone.

### 10. Rule of three

AI defaults to triplets ("innovation, inspiration, and insights"). Use two,
four, or one specific item.

Before: The event features keynotes, panels, and networking. Attendees can
expect innovation, inspiration, and industry insights.
After: The event has talks and panels, with time for informal networking
between sessions.

### 11. Elegant variation / synonym cycling

The repetition penalty makes AI cycle synonyms within a single passage:
"the protagonist… the main character… the central figure… the hero…".

Before: The protagonist faces many challenges. The main character must
overcome obstacles. The central figure eventually triumphs. The hero returns
home.
After: The protagonist faces many challenges but eventually triumphs and
returns home.

### 12. False ranges

"From X to Y" where X and Y aren't on a single scale.

Before: Our journey through the universe takes us from the singularity of
the Big Bang to the grand cosmic web, from the birth and death of stars to
the enigmatic dance of dark matter.
After: The book covers the Big Bang, star formation, and current theories
about dark matter.

### 13. Passive voice / subjectless fragments

Before: No configuration file needed. The results are preserved
automatically.
After: You don't need a config file. The system preserves results
automatically.

---

## Style & formatting tells

### 14. Em dashes and en dashes — cut them all

The single most reliable AI tell. The final rewrite contains **zero** `—`
and zero `–`. Replace, in order of preference:

- period (start a new sentence)
- comma (tight aside)
- colon (introducing explanation)
- parentheses (true aside)
- restructure

Catch the spaced variants ` — ` and the double hyphen ` -- ` too.

Before: The new policy — announced without warning — affects thousands of
workers.
After: The new policy, announced without warning, affects thousands of
workers.

Before delivery, search the draft for `—` and `–`. Any hit means you're not
done.

### 15. Decorative bold

Mechanical bolding of every key noun.

Before: It blends **OKRs**, **KPIs**, and tools like the **Business Model
Canvas** and **Balanced Scorecard**.
After: It blends OKRs, KPIs, and tools like the Business Model Canvas and
Balanced Scorecard.

### 16. Inline-header vertical lists

`- **Topic:** sentence restating Topic.`

Before:
- **User Experience:** The user experience has been improved with a new
  interface.
- **Performance:** Performance has been enhanced through optimization.

After: The update adds a new interface, optimizes load times, and enables
end-to-end encryption.

### 17. Title Case Headings In Body Copy

Reserve title case for actual titles. Body headings should be sentence case.

Before: ## Strategic Negotiations And Global Partnerships
After:  ## Strategic negotiations and global partnerships

### 18. Decorative emoji

Headings and bullet points decorated with 🚀 / 💡 / ✅ for no reason.

Before: 🚀 **Launch Phase:** The product launches in Q3.
After:  The product launches in Q3.

### 19. Curly quotes

ChatGPT defaults to `"…"` smart quotes. If the surrounding text is plain
ASCII, normalize to `"…"`. (Curly quotes alone are not a tell — many CMSes
auto-curl — but they count as evidence when paired with others.)

---

## Communication artifact tells

### 20. Chat-mode artifacts pasted as content

Watch: *Of course! Certainly! You're absolutely right! Would you like me to…?
Let me know. Here is a… I hope this helps.*

Before: Here is an overview of the French Revolution. I hope this helps! Let
me know if you'd like me to expand on any section.
After: The French Revolution began in 1789 amid financial crisis and food
shortages.

### 21. Cutoff disclaimers & speculative gap-filling

Watch: *as of my last training update, while specific details are scarce,
based on available information, maintains a low profile, keeps personal
details private, likely [grew up / studied].*

Two related tells. (a) Hard cutoff disclaimers left in the text. (b) When the
model can't find a source it writes a paragraph *about* not finding one and
then invents plausible filler.

Before: Information about her early life is not publicly available,
suggesting she maintains a low profile. She likely grew up in a middle-class
household.
After: Her early life is not documented in available sources. (Or cut the
sentence.)

### 22. Sycophantic openers

Before: Great question! You're absolutely right that this is a complex
topic.
After: The economic factors you mentioned are relevant here.

---

## Filler, hedging, and rhetorical tells

### 23. Filler phrases

| Before | After |
|---|---|
| In order to achieve this goal | To achieve this |
| Due to the fact that it was raining | Because it was raining |
| At this point in time | Now |
| In the event that you need help | If you need help |
| The system has the ability to process | The system can process |
| It is important to note that the data shows | The data shows |

### 24. Excessive hedging

Before: It could potentially possibly be argued that the policy might have
some effect on outcomes.
After: The policy may affect outcomes.

### 25. Generic positive conclusions

Before: The future looks bright for the company. Exciting times lie ahead
as they continue their journey toward excellence.
After: The company plans to open two more locations next year.

### 26. Hyphenated compound overuse (in predicate position)

Watch: *third-party, cross-functional, client-facing, data-driven,
decision-making, well-known, high-quality, real-time, long-term, end-to-end.*

AI hyphenates uniformly. Humans typically hyphenate only attributively (`a
high-quality report`) and drop the hyphen in predicate position (`the report
is high quality`).

Before: The team is cross-functional, the report is high-quality, and the
methodology is data-driven.
After: The team is cross functional, the report is high quality, and the
methodology is data driven.

### 27. Persuasive authority tropes

Watch: *the real question is, at its core, in reality, what really matters,
fundamentally, the deeper issue, the heart of the matter.*

These pretend to cut through noise to a deeper truth. Usually the sentence
that follows just restates an ordinary point with extra ceremony.

Before: The real question is whether teams can adapt. At its core, what
really matters is organizational readiness.
After: The question is whether teams can adapt. That depends on whether the
organization is ready to change its habits.

### 28. Signposting and announcements

Watch: *Let's dive in, let's explore, let's break this down, here's what you
need to know, now let's look at, without further ado.*

Before: Let's dive into how caching works in Next.js. Here's what you need
to know.
After: Next.js caches data at multiple layers: request memoization, the data
cache, and the router cache.

### 29. Fragmented headers

A heading followed by a one-line paragraph that restates the heading before
the real content begins.

Before:
## Performance
Speed matters.
When users hit a slow page, they leave.

After:
## Performance
When users hit a slow page, they leave.

### 30. Diff-anchored writing

Documentation written as if narrating a change rather than describing the
thing as it is.

Before: This function was added to replace the previous approach of iterating
through all items, which caused O(n²) performance.
After: This function uses a hash map for O(1) lookups, avoiding the O(n²)
cost of naive iteration.

### 31. Manufactured punchlines / staccato drama

A run of short declarative fragments to manufacture drama. A single short
sentence is fine; a stack of them sounds engineered.

Before: Then AlphaEvolve arrived. It had no preference for symmetry. No
aesthetic prior. No nostalgia for human taste. The old rules were gone.
After: AlphaEvolve changed the search because it didn't favor symmetry or
human-looking designs. That made some older assumptions less useful.

### 32. Aphorism formulas

Watch: *X is the Y of Z, X becomes a trap, X is not a tool but a mirror, the
language of, the currency of, the architecture of.*

Before: Symmetry is the language of trust. Efficiency becomes a trap when
teams forget the human layer.
After: Symmetric layouts feel more predictable to users. Teams can
over-optimize workflows and miss how people actually use them.

### 33. Conversational rhetorical openers

Watch: *Honestly?, Look, Here's the thing, The thing is, Let's be honest,
Real talk* — used as standalone hooks before an ordinary point.

Before: Is it worth the price? Honestly? It depends on how often you'll use
it.
After: Whether it's worth the price depends on how often you'll use it.

---

## False positives — don't flag these alone

A clean human writer can hit several patterns above without any AI
involvement. Treat the following as **evidence only in clusters**:

- Polished grammar and consistent style (editors exist)
- Mixed casual/formal register (often a technical writer)
- Formal vocabulary that isn't on the AI-cluster list (*ostensibly*,
  *constituent*, *moreover* in isolation)
- One em dash, one curly quote, one "however" — alone they mean nothing
- Letter-style salutations and sign-offs (predate ChatGPT by centuries)
- Visual templates producing clean output

Strong **human** signals (preserve, don't edit out):

- Specific, unusual, hard-to-fabricate detail
- Mixed feelings and unresolved tension
- Dated, era-bound slang or in-jokes
- Genuine asides and self-corrections
- Variety in sentence length
