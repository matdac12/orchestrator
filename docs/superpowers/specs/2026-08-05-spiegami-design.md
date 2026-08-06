# spiegami — design

**Date:** 2026-08-05
**Status:** approved, ready for implementation

## Purpose

After a long investigation or a big decision, the conversation holds a lot of reasoning
that Mattia has not fully internalised. `spiegami` breaks that reasoning into a chain of
small links and teaches them one at a time, in plain language, with a comprehension check
between each one.

It is a **retrace tool**, not a tutorial generator. Every example comes from the real
material in the conversation — the real file, the real decision, the real error.

## Scope

**In scope:** the current conversation only. The skill reads what is already in context.

**Out of scope** (decided, not deferred):

- Reading files, specs, diffs or PRs named by the user.
- Free-form topics with no local material ("teach me how RLS works").
- Writing any output file.
- Any subagent. The skill runs in the main session, because the main session is what holds
  the context.

## Placement

- File: `.claude/skills/spiegami/SKILL.md` in the orchestrator repo. Single file, no
  reference files — the writing rules are needed on every run, so a separate file that must
  always be read adds a step with no benefit.
- Junctioned into `~/.claude/skills/spiegami` so it is available in every project.
  Per-directory junction, as with the other skills in this hub.
- Frontmatter: `name: spiegami`, `user-invocable: true`, `disable-model-invocation: true`,
  plus a short human-facing `description`.

## Trigger

**Human-only.** `disable-model-invocation: true` removes the skill from the model's Skill
tool, so Claude cannot start it and its description does not sit in the skill list of every
session. This keeps the agent's context clean — the reason for the setting.

The only trigger is the slash command: `/spiegami`, optionally with a language override
(`/spiegami in italiano`). Plain-language phrasings — "spiegami passo passo", "walk me
through this" — do **not** start the skill, because starting it from those words would be
model invocation, which is exactly what is switched off.

Because the model never invokes it, the `description` is written for the human reading the
slash-command menu, not as a trigger list for the model.

If the conversation holds no substantial material, the skill says so and asks what to cover.
It does not invent a topic.

## Flow

1. **Build the chain.** Read the conversation. Split it into links. Order the links so each
   one uses only what earlier links taught. The first link assumes zero prior knowledge.
2. **Show the map.** Bullet list, one short sentence per link. No paragraph. This gives the
   shape and the length, nothing more.
3. **Teach one link.** About 150 words, hard ceiling. One idea. One concrete example taken
   from the real material.
4. **Check.** Ask whether the link is clear — "Tutto chiaro?" — then stop and wait. The
   check is a yes/no question about the explanation, never a quiz on the content and never
   a decision for the human. The skill never moves to the next link on its own.
5. **The human steers.** Any feedback — "clearer", "another example", "too fast", "skip it" —
   is answered as asked. There is no fixed remediation script and no forced sub-decomposition.
   A side question gets answered, then the skill returns to the same link.
6. **Recap.** After the last link, one line per link, the whole chain in one view. Then stop.
   Nothing is written to disk.

## Writing rules

ASD-STE100's *rules*, not its dictionary. The approved word list is aviation-specific, has no
Italian equivalent, and makes text read like a machine, which is bad for teaching. The rules
themselves solve the actual problem: a large model writing in heavy words.

- One idea per sentence. Under about 20 words.
- Active voice. "The hook runs the script", not "the script is run by the hook".
- One name per thing, always the same one. Never a synonym for variety.
- Concrete verbs. Use "use", "help", "run" when they are true, not "leverage", "facilitate",
  "orchestrate".
- Explain a term the first time it appears, in the same sentence.
- Never two unexplained terms in one sentence.
- No hedging filler: "it's worth noting that", "essentially", "in some sense".

The same rules apply in Italian.

## Language

The skill follows the language the human is writing in. An explicit request overrides it
(`/spiegami in inglese`, `/spiegami in italiano`).

In Italian, technical nouns keep the form actually used in Italian tech speech: *worktree*,
*deploy*, *junction*, *subagent*, *RLS*. Translations are not invented.

## Naming

`spiegami` was chosen over `teach-me-like-im5`. It matches the house style of this hub
(`esegui-test`, `prepara-test`), it is short to type, and it does not carry the
"baby talk and ice-cream analogies" promise of ELI5, which is not what this skill does.
Routing is driven by the `description` field, not by the name.

## Success criteria

- Invoked after a long session, the skill produces a map whose first link needs no prior
  knowledge, and whose order never uses a term before teaching it.
- Every link stays under the length ceiling and ends by waiting for the human.
- Examples come from the conversation, not from generic invented cases.
- Italian output reads as normal Italian tech speech, not as translated English.
