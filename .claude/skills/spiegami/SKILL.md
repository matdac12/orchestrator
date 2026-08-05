---
name: spiegami
description: Use when the human asks to be walked through something one step at a time — "spiegami", "spiegami passo passo", "fammi capire", "explain this to me step by step", "walk me through what we just decided", "retrace this for me", "teach me what we just built". Also use when the human says an explanation was too dense, too fast, or too full of jargon, or after a long investigation or a big decision when they want to own the reasoning themselves.
user-invocable: true
---

# Spiegami

## Overview

Break the reasoning already in this conversation into a chain of small links.
Teach one link. Stop. Wait for the human.

This is a **retrace tool**, not a tutorial. Every example comes from the real material in
this conversation — the real file, the real decision, the real error. Never a generic
invented case.

## When to use

- After a long investigation or a big decision, when the human wants to understand it and
  not just accept it.
- When an earlier explanation was too dense, too fast, or too full of jargon.

**When not to use:** there is nothing substantial in this conversation to teach. Say that
plainly and ask what to cover. Do not invent a topic. Do not go read files or a diff to
manufacture material — this skill teaches what is already here.

## Build the chain

Read the conversation. Split it into links.

- A link is **one idea**, not one topic. "What a worktree is" is a link. "How the
  orchestrator works" is five links.
- Order the links so each one uses only what earlier links already taught.
- Link 1 assumes zero prior knowledge.
- If a term appears in link 4, some earlier link must have taught it.

## Show the map, then teach link 1

Show the map as bullets, one short sentence each. No paragraph. It gives the shape and the
length, nothing more.

Then teach link 1 **in the same message**. There is no approval gate on the map.

## One link has these parts, in order

1. **The name of the thing**, in one sentence.
2. **What it does**, in plain words.
3. **One example from this conversation** — a real path, a real command, a real decision.
4. **Why it matters**, in one sentence: what breaks or gets harder without it.
5. **The check** — a short question, then stop.

Parts 1 to 4 stay under about 150 words in total. That is a ceiling, not a target.

## Stop after every link

**One link per message. Always.**

After the check question, stop and wait. Do not teach the next link until the human replies.

| Rationalization | Reality |
|---|---|
| "These two links are tightly related" | Two links, two messages. |
| "The next one is short and obvious" | Then it costs almost nothing to send it separately. |
| "They said yes fast, they are following" | "Yes" means *next link*, not *all links*. |
| "Batching is more efficient" | The gate is the skill. Batching deletes it. |
| "I already showed the map, so they know" | The map is orientation. It teaches nothing. |

## Writing rules

Use the rules of ASD-STE100 Simplified Technical English, not its word list:

- One idea per sentence. Under about 20 words.
- Active voice. "The hook runs the script", not "the script is run by the hook".
- One name per thing, always the same one. Never a synonym for variety.
- Concrete verbs. Use "use", "help", "run" when they are true — not "leverage",
  "facilitate", "orchestrate".
- Explain a term the first time it appears, in the same sentence.
- Never two unexplained terms in one sentence.
- No hedging filler: "it's worth noting that", "essentially", "in some sense".

The same rules apply in Italian.

## Language

Follow the language the human is writing in. An explicit request overrides it
(`/spiegami in inglese`, `/spiegami in italiano`).

In Italian, keep technical nouns in the form Italian developers actually say: *worktree*,
*deploy*, *junction*, *subagent*, *RLS*, *commit*. Do not invent Italian translations for
them. Everything around them is normal Italian.

## Let the human steer

Any feedback is an instruction. "Clearer", "another example", "too fast", "skip this one" —
do what was asked, in whatever way works best. There is no fixed remediation script and no
forced sub-splitting.

A side question gets answered, then return to the same link.

## The end

After the last link: one line per link, the whole chain in one view. Then stop.

Write nothing to disk unless the human asks.

## Red flags — stop and fix

- More than one link in a message.
- An example that did not come from this conversation.
- A sentence over about 20 words.
- A term used before some earlier link explained it.
- A link that ends without a question.
- A recap that is longer than one line per link.
