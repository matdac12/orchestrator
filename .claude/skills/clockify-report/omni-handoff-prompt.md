Add Clockify time-logging tools to Omni, so I can log my hours from WhatsApp.

Everything you need is already on this box:

- `~/.claude/skills/clockify-report/SKILL.md` — the behaviour spec. Read it first.
  It is written for a Claude Code skill, not for you, so translate it: the "pass",
  the confirmation gate, the description style and the failure table all carry over;
  the CLI ergonomics do not.
- `~/.claude/skills/clockify-report/clockify.py` — a working, tested reference
  implementation of every API call you need (fuzzy project matching, Europe/Rome →
  UTC with a DST fallback, the overlap guard, error mapping). Port the logic, don't
  shell out to it.
- `CLOCKIFY_API_KEY` is already in `.env`. Nothing to provision.

Build it exactly the way the Linear integration was built earlier today — that is the
pattern to mirror, file for file:

- `src/clockify/{__init__.py,client.py}` — async client, like `src/linear/client.py`.
  Raise a `ProjectNotFound` carrying the candidate list, the same way Linear does.
- `src/agent/toolkit/clockify.py` — self-registering tools, like `toolkit/linear.py`.
- `src/config.py` — a `CLOCKIFY_API_KEY` / `CLOCKIFY_API_URL` block next to the Linear one.
- Add `"src.agent.toolkit.clockify"` to `_BUILTIN_MODULES` in `toolkit/registry.py`.
- `tests/test_clockify.py`, mirroring `tests/test_linear.py`. No network in tests.

Owner-only, and hidden entirely when the key is missing — copy `_is_owner_with_key`
from `toolkit/linear.py`.

## Tool surface

Three tools. Descriptions in Italian, like the HubSpot ones.

`clockify_projects(query?)` — fuzzy search over project **and** client name, returning
id, name, client and score. No query returns my ~6 most recently used. There are 58
active projects, so never return them all.

`clockify_recent(limit?, project?)` — recent entries with local times and descriptions.
Two purposes: showing me what I already logged, and reusing the last description on a
project when today's work continues yesterday's.

`clockify_log(project, date, start, end, description, billable?, allow_overlap?)` —
the only write.

- `project` is **the name as I said it on WhatsApp**, not an id. Resolve it server-side.
  Ambiguous or unknown comes back as an error carrying the candidates, so the model can
  retry — same contract as Linear's `ProjectNotFound`. Do not make the model do a
  two-step id lookup; on WhatsApp that is a wasted round trip.
- `date` accepts `YYYY-MM-DD`, `oggi`, or `ieri`, **resolved server-side in Europe/Rome**.
  This is deliberate: a model that guesses today's date writes a silently wrong billable
  record, so don't let it do the arithmetic.
- `requires_approval=True` with a `render_approval` — see `toolkit/hubspot.py`
  (`hs_create_deal`). This *is* the confirmation gate from the skill: the preview above
  the Approva/Rifiuta buttons must be one Italian line carrying date, times, duration,
  **project and client both**, description, and billable state:

  `07/08/2026 08:30-12:30 (4h) · YOUR-BRAIN · ORANGE 1 · Lavoro al CRM, sistemate le esposizioni dati · fatturabile`

  Project and client together is not decoration — I have two projects called
  `Attività Commerciale` and two called `Progetto Amministrazione`, distinguished only
  by client.

## Behaviour to carry over from the reference implementation

- Local times are Europe/Rome; Clockify stores UTC. `zoneinfo` exists here, so use it —
  the hand-rolled EU DST rule in the reference is a Windows fallback you don't need.
- **Overlap guard.** Before writing, check that day's existing entries; if the new block
  overlaps one, return an error naming the conflicting entry rather than writing.
  `allow_overlap` forces it. Double-logging is the failure mode this catches.
- Billable by default. Tasks and tags are unused in my workspace — leave them alone.
- Reject `end <= start`; no overnight entries.
- A submitted/approved week is locked and rejects writes (HTTP 403/400 mentioning
  approval). Surface that as "quella settimana è chiusa" and stop — retrying cannot work.
- Entries are authored by whoever owns the key, so they land on my timesheet. There is
  no path here that writes to a colleague; don't add one.

## The description field

This is the part that matters most and the part a model gets wrong. My entries are one
line of plain Italian, past work stated flatly. Real ones:

> Lavoro al CRM, miglioramento esposizioni dati nell'interfaccia e risoluzione bugs
> Investigazione contatti Klaviyo, inizio preparazione progetto portale Listini
> Sincronizzazione contatti CRM attuale col nuovo e tests
> Allineamento con Kety e Franco per Galaxus, MRP, Mail Automatiche, e Klaviyo

Put that guidance in the tool description itself — on WhatsApp there is no skill file to
load. Name the concrete thing (the CRM, the Klaviyo contacts, the staging table), never
the activity class ("sviluppo", "attività"). If I haven't said what I did, the tool
description must tell the model to **ask me in plain text** rather than invent something
plausible: it is going into a billable record.

Same rule for the time. If I say "logga 2 ore su Zafferano" without hours, ask — one
ordinary sentence, "che orario?" — don't assume a block. My days are irregular; I log
21:00-23:00 as readily as a standard morning.

## Finally

Run the tests. Then tell me what to restart and let me do it — `whatsapp-omni.service`
is live and I'd rather bounce it myself. Don't send me a WhatsApp message to test; I'll
drive the first real entry by hand.
