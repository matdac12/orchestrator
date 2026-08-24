---
name: clockify-report
description: Logs Mattia's hours to Clockify — pick the project, resolve the day and times he says in plain language, draft the Italian description from the work actually done, confirm, write. Use when he asks to log/track hours, "rendiconta", "segna le ore", "/clockify-report", or names a block of time to put on a project.
disable-model-invocation: true
user-invocable: true
---

# clockify-report

Turn "logga 8:30-12:30 su Orange" into a Clockify entry, with the description
written for him rather than by him. One entry per pass, then offer another.

```bash
S=~/.claude/skills/clockify-report/clockify.py   # stable path — on Windows a junction into the orchestrator repo
python "$S" projects --search "orange crm"
python "$S" log --project-id 6a21... --date 2026-08-07 --start 08:30 --end 12:30 \
  --description "Lavoro al CRM, sistemate le esposizioni dati" --dry-run
```

## The pass

1. **Project.** Ask him which one, unless he already named it in the
   invocation. He answers with a name or a fragment — "orange", "zafferano",
   "molino corso ai", and it will often be misspelled. Run
   `projects --search "<what he said>"` and **propose the top match for
   confirmation**, by project *and* client name. Never write to a project he
   hasn't confirmed by name, however confident the score.

   Show the shortlist instead of a single proposal when the top score is under
   **0.60**, or when the runner-up is within **0.10** of it — a near-tie means
   the fragment was ambiguous, not that you should pick. `projects` bare gives
   his recent six for when he doesn't know what the thing is called. Never dump
   all 58.

   Do not infer the project from the repo you happen to be in. He logs meetings,
   calls and analysis from directories that have nothing to do with the client.
   This is the one step where a multiple-choice question earns its place: the
   options are a closed set you just fetched, and picking by name is the
   confirmation. Everything below is open text — see *Asking him things*.
2. **Time.** Parse what he said. If he said nothing about it, ask — together
   with the description, in one plain-text question. Never propose candidate
   blocks. Echo the resolved date and times back inside the confirmation line,
   never as a separate follow-up question.
3. **Description.** Draft it (below). Show it as part of the confirmation. If
   you have no signal, ask in the same question as the time.
4. **Confirm.** One line, explicit yes required. See the gate.
5. **Write**, print the result, then ask: *ne aggiungo un'altra?* If yes, start
   over at 1 — carrying nothing over except the date.

## Asking him things

**Project → offer a list. Time and description → ask in plain text.**

A multiple-choice tool on an open field doesn't merely fail to help, it proposes
wrong answers with an air of authority. Times are irregular — he logs 21:00-23:00
and 13:30-18:30 as readily as a standard morning — so any block you generate from
his history is a guess dressed as a suggestion, and putting `08:30-12:30` first
makes the near-enough option the path of least resistance. On a billable record
that is exactly the wrong bias. Same for the description: offering phrasings
invites him to accept one that is close, when the value of the field is that it
is precise.

So when the time or the work is unknown, write one ordinary sentence and let him
answer in his own words:

> Su Zafferano — che orario, e cosa hai fatto?

He replies `21-23, set up e inizio sviluppo portale Listini` and you go straight
to the confirmation line. One round trip, not two. When he already named the
project in the invocation — the normal case — that single question is the only
one you should need before the gate.

## Writing the description

His entries are one line of plain Italian, past work stated flatly, no bullet
points and no ceremony. Real ones:

> Lavoro al CRM, miglioramento esposizioni dati nell'interfaccia e risoluzione bugs
> Investigazione contatti Klaviyo, inizio preparazione progetto portale Listini
> Sincronizzazione contatti CRM attuale col nuovo e tests
> Allineamento con Kety e Franco per Galaxus, MRP, Mail Automatiche, e Klaviyo

Draft from what actually happened — this session's work, the commits on the
branch, the call he just described. **Italian, always**, even when the
conversation is in English. Name the concrete thing (the CRM, the Klaviyo
contacts, the staging table), not the activity class ("sviluppo", "attività").

`recent --project-id <id>` shows what he last wrote on that project. When the
work is genuinely the continuation of it, reuse that line rather than inventing
a fresh phrasing — he repeats descriptions across days on purpose.

If you have no real signal about the work, **ask**. A plausible-sounding
invented description is worse than a question: it goes into a billable record.

## Reading the time

Resolve to a concrete date and HH:MM yourself; the script is strict.

| He says | You pass |
|---|---|
| `8:30-12:30`, `dalle 8:30 alle 12:30` | today, `--start 08:30 --end 12:30` |
| `ieri pomeriggio 14-16` | yesterday, `14:00`→`16:00` |
| `4h dalle 8:30`, `mezza giornata da stamattina` | start + duration |
| `lunedì`, `il 3` | that date in the current week / month |
| nothing about time | ask, in plain text — never propose candidate blocks |

**Get today's date from the environment, not from memory** — your sense of the
date drifts and a wrong day is a silent, wrong billable record. `stamattina`
with no hours usually means a start of 08:30 — confirm it in the line rather
than assuming it silently. Do not let that hour anchor anything else: his real
entries run late evenings and long afternoons as often as standard mornings, so
a block you did not hear from him is a guess, whatever his usual day looks like.

Times are local (Europe/Rome). The script converts to UTC, DST included, and
refuses entries that end before they start. No overnight entries.

## The gate

Never call `log` without `--dry-run` until he has said yes to a line like:

```
07/08/2026 08:30-12:30 (4h) · YOUR-BRAIN · ORANGE 1 · Lavoro al CRM, sistemate le esposizioni dati · fatturabile
```

Project *and* client, both — he has two projects called `Attività Commerciale`
and two called `Progetto Amministrazione`, distinguished only by client.

"yes", "ok", "vai" is consent. Silence, a new question, or a change to one field
is not — re-show the line after any edit. Everything is billable unless he says
otherwise (`--no-billable`); tasks and tags are unused in his workspace, leave
them alone.

## Commands

| | |
|---|---|
| `whoami` | identity, workspace, which timezone path is active |
| `projects` | his six most recently used, newest first |
| `projects --search Q` | fuzzy over project **and** client name, scored, top 6 |
| `recent [--limit N] [--project-id X]` | recent entries with local times and descriptions |
| `log --project-id --date --start --end --description` | the only write. `--dry-run`, `--no-billable`, `--allow-overlap` |
| `delete --id X` | remove an entry — for undoing a test write |

## When it fails

| Exit | Meaning | Do |
|---|---|---|
| 0 | Written | Report the line and the id. |
| 3 | Overlaps an existing entry | Show him the conflicting entry the script printed. It is usually a double-log — ask before passing `--allow-overlap`. |
| 1, HTTP 401 | Key rejected | The key was rotated. He replaces `~/.claude/.clockify-api-key`; nothing else to try. |
| 1, HTTP 403/400 mentioning approval | That week is submitted and locked | Say so and stop. Retrying cannot work — an admin has to reopen it. |
| 2 | Bad arguments or no key | Yours to fix. Nothing was sent. |

Any non-zero exit means **nothing was logged**. Say that plainly — he reads a
quiet reply as an entry that landed.

## Configuration

- Key: `$CLOCKIFY_API_KEY`, else `~/.claude/.clockify-api-key`. That file sits
  outside every checkout, so it cannot be committed by accident. Never print it.
- Workspace and user id come from `/user` on every call — nothing is hardcoded.
- **Entries are always authored by whoever owns the key.** `POST /time-entries`
  writes for the authenticated user, so with his personal key the entry lands on
  Mattia Da Campo's timesheet; there is no path here that logs hours against a
  colleague. `log` prints `as: …` on every write, dry run included — if that
  ever shows someone else, the key file is wrong and the entry is on the wrong
  person's timesheet. Stop and tell him.
- Stdlib only. Falls back to a built-in EU DST rule when Windows Python ships
  without the IANA timezone database, so no pip install is ever needed.
