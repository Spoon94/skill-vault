---
name: clarify
description: Rewrite deliverable text into controlled language — English (ASD-STE100) or Chinese (受控中文) — one meaning per word, active voice, short sentences, one instruction per sentence. Use when asked to clarify / simplify text/wording / disambiguate output, apply STE / STE100 / controlled English, make text safe for downstream agents, or non-native readers; or 消除歧义 / 受控中文 / 精简交付文本 / 重写 / 改写 / 术语统一 / 规范化用词.
license: MIT
allowed-tools: Read Grep Glob
metadata:
  origin: derived
  upstream: https://github.com/kv0906/cc-skills/tree/main/explain-to-me/skills/asd-ste100
---

# clarify — Controlled-Language Rewriting (EN/ZH)

Rewrite the **final deliverable text** into a controlled language: **ASD-STE100** for English, **受控中文 (controlled Chinese)** for Chinese. The rules apply **only to the output layer** — never let them leak into your reasoning, analysis, or drafting.

> **Hard rule — constraint placement.** Do all thinking, exploring, and drafting in normal full language first. Apply the controlled rewrite **only as the last transformation**, right before presenting text the user will consume or hand to another agent. Do not "write simply while you think" — enforced at the thought level it measurably degrades reasoning quality. Think freely, then constrain the surface.

## Scope

Use when the text will be **read by a human who needs unambiguous content** — or consumed by a downstream machine / non-native reader with no one to ask a follow-up question:

- Deliverables a person must act on correctly: instructions, reports, explanations, documentation. (STE's original purpose and Karpathy's use: "a lot more readable" for humans.)
- Agent-to-agent messages, tool / function descriptions, error messages, system prompts
- Instructions handed to another agent, a translation pipeline, or a downstream system
- Any output where a misread carries real cost — for a human or a machine

**Do not use** for creative writing, marketing copy, persuasive text, or anything where voice and nuance are the point. Controlled language is deliberately flat and literal.

> **Not for humanizing — both serve humans.** `deslop-bi` makes text **read naturally** (de-AI-flavored, restores human voice); this skill makes text **read precisely** (controlled, unambiguous). 要人性化用 `deslop-bi`；要精确无歧义用本 skill。

## Language selection

- Input is English → rewrite to **STE** (rules below).
- Input is Chinese → rewrite to **受控中文** (rules below).
- Mixed input → follow the dominant language; preserve code, commands, paths, API names, and identifiers **exactly** in both modes.

## Shared principles (both languages)

| Principle | Do | Don't |
|---|---|---|
| One word, one meaning | Pick one term per concept; reuse it every time | Rotate synonyms for the same idea |
| Name the actor | EN: always make the subject explicit · ZH: 主体不明时必须补（明确时可省） | Drop the subject |
| Active voice | "The agent deletes the file." / 「agent 删除文件」 | Passive with unclear actor |
| One instruction per sentence | Split compound instructions | Chain actions with "and then" / 「然后」「并」 |
| Short sentences | ≤20 words (EN instructions), ≤25 (EN descriptions); ≤30 字 (中文指令), ≤40 字 (中文描述) | Long compound sentences |
| Lists for sequences | Numbered/bulleted list for 3+ steps | Bury a sequence in one prose sentence |
| Preserve precision | Keep every fact, condition, exception, number, **and degree of certainty**（可能/大概/也许/一定 原样保留） | Simplify away a safety condition or scope limit |

## English rules (ASD-STE100)

| Rule | Do | Don't |
|---|---|---|
| One part of speech per word | Use a word only in its approved role | "Oil the valve" when "oil" is a noun only |
| Simple tenses only | "We received the report." | "We have received the report." |
| Noun clusters | ≤3 words | 4+ word noun stacks |
| No ellipsis | Keep subject, verb, article explicit | Drop words to save space |
| Paragraph limits | One topic per paragraph, ≤6 sentences | Multi-topic paragraphs |

Common replacements: `prior to`→`before`, `utilize`→`use`, `commence`→`start`, `ensure`→`make sure`, `replenish`→`fill`, `approximately`→`about`, `in order to`→`to`.

## 中文规则（受控中文）

| 规则 | 要求 | 反例 |
|---|---|---|
| 主体不明时必补主语 | 动作主体明确时可省略；不明或可能歧义时必须补出 | 「删除文件」（谁删？若上下文不明则必补） |
| 少用「被」字句 | 「服务验证 token」 | 「token 被验证」 |
| 一句一个动作 | 「打开文件。读第 3 行。」 | 「打开文件并读第 3 行，然后检查是否匹配」 |
| 一词一义 | 同一动作全程用同一个词 | 「检查 / 核查 / 验证」混用指同一动作 |
| 直接动词 | 「分析数据」 | 「对数据进行分析」（去掉「进行…的」壳）|
| 术语先定义 | 首次出现行话立即解释 | 行话用到底不解释 |
| 短定语 | 定语拆成短句 | 「那个负责管理所有上游任务队列优先级分配的处理器的配置」 |
| 的的不休 | 「A 的 B」→ 拆为短句或改为动宾结构 | 三个及以上「的」连用，如「系统的配置的更新的时间」 |
| 标点数字统一 | 阿拉伯数字用于计量/编号；中文数字用于约数/惯用；逗号连接完整句用句号断开 | 「3个」、「约5个」混用；一逗到底 |
| 条件前置 | 条件写在动作前：「如果被锁定，跳过。否则，删除文件」 | 「删除文件。如果被锁定则跳过」（先命令后条件） |
| 同名同物不合并 | 不同实体必须用不同名；指代不明时标为问题让用户确认 | 两个实体挤进一个名字；指代不明时擅自猜一个意思 |
| 保确定性 | 确定性标记（可能/大概/也许/一定）原样保留，不可丢——删「可能」引此条。定义见 Shared 表 Preserve precision | 重写时丢掉「可能」，把猜测洗成断言 |
| 语义不升级 | 确定性等级不可跳——「可能」→「一定」引此条。两行分工：标记丢=保确定性；等级跳=语义不升级 | 可能原因→既定事实；建议→要求 |

常见替换：「利用」→「用」，「进行 X」→「X」，「通过…来」→直接动词，「务必」→「必须」或删，「相关」→写明具体关系，「妥善」→写明具体动作。

## Optional intensity: `~80%`

By default apply the rules fully. If the user asks for a softer pass ("80% of the way" / 「八成力度」), apply the word-choice and voice rules but relax the hard length caps — ambiguity removed, meaning exact, short of the strictest form. Always state which level you applied.

## Process

1. Read the input once for meaning. Do not rewrite before you understand what it must still say.
2. Flag every violation sentence by sentence.
3. Rewrite each flagged sentence, **preserving every fact, condition, exception, scope qualifier, and number exactly**. If a shorter phrasing would drop required precision (a safety condition, a scope limit), keep the longer phrasing and flag the trade-off — never silently simplify.
4. Produce the before/after table.
5. If the input already complies, say so. Do not force changes onto compliant text.
6. **对照自检（Audit）**——把原文和改写稿对照，主动找三类问题并列出：
   - **新增**：改写稿里有没有原文没有的内容（模型自己加的）
   - **遗漏**：原文内容有没有丢
   - **变义**：意思有没有被偷换（含确定性丢失——引「保确定性」；语义升级——引「语义不升级」）

Input text: $ARGUMENTS — 若无参数，处理当前对话中的交付文本。

## Output contract

Return:

1. The **rewritten text** (controlled-language applied).
2. A **before/after table** of changed sentences, with the rule violated:

```markdown
| Rule violated / 违反规则 | Original | Rewritten |
|---|---|---|
| Present perfect tense | "We have received your request." | "We received your request." |
| 主体不明时必补主语 | 「完成后更新状态」 | 「任务完成后，agent 更新状态」 |
```

3. A short **left-unsimplified** note for anything deliberately kept long (and why).

4. An **audit report** — the self-check from step 6:

```markdown
## Audit / 对照自检
- 新增: <改写稿中原文没有的内容，或 "无">
- 遗漏: <原文中丢失的内容，或 "无">
- 变义: <语义被改变处，或 "无">
```

## References

- `references/writing-rules.md` — ASD-STE100 rule summary and sources (from `kv0906/cc-skills/asd-ste100`, MIT)
- `examples/before-after.md` — official-rule illustrations + agent-output examples
- Official standard (free download): https://www.asd-ste100.org/

The English mode applies the *principle* (plainest available word, used the same way every time) rather than checking against ASD's ~900-word approved dictionary. The Chinese mode is an original adaptation of the same principles — there is no official controlled-Chinese standard. For certified STE-compliant documentation, check word-by-word against the real dictionary.
