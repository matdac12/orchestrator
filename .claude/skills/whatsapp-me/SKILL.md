---
name: whatsapp-me
description: Sends Mattia a WhatsApp message right now — to report that a long job finished, that it failed, or that you need him back at the terminal. Fires immediately when he types /whatsapp-me; never on your own initiative.
disable-model-invocation: true
user-invocable: true
---

# whatsapp-me

Send Mattia one WhatsApp message, now, via the bedigital-omni endpoint.

`/whatsapp-me` is the only trigger. Mattia types it; you send. Do not reach for
this skill because a task ran long, because something broke, or because a ping
seems helpful — an unrequested message goes to his phone.

## Send it

```bash
python "C:/Users/MattiaDaCampo/Documents/orchestrator/.claude/skills/whatsapp-me/notify.py" "migration finished, 0 failures"
```

To send command output — test failures, a stack trace, a diff summary — pipe it
instead of pasting it into the argument:

```bash
pytest 2>&1 | tail -40 \
  | python ".../notify.py" --stdin --prefix "TESTS FAILED"
```

**Always pipe rather than interpolate.** `-d "{\"text\": \"$MSG\"}"` breaks the
moment the text holds a quote, newline, or backslash — which is precisely what
test output holds. `notify.py` builds the JSON with `json.dumps`, so piping is
safe; hand-built payloads are not.

## Write the message for a phone

One or two lines. Lead with the outcome, then what it means for him.

- `DONE - migration applied, 0 failures. Safe to push.`
- `FAILED - 3 tests red in auth/. Stack trace in the terminal.`
- `NEED YOU - schema change is ambiguous, I stopped before writing.`

Not the full reply, not file paths, not code — those stay in the terminal.

## When it doesn't arrive

Exit 0 prints `whatsapp-me: sent`. **Any other exit means the message did not
reach his phone**, and you must say so in the terminal — Mattia reads a missing
ping as a job still running.

| Exit | Meaning | Do |
|------|---------|-----|
| 0 | Delivered | Nothing. If it says `(truncated by the endpoint)`, the tail was cut — send the rest or shorten. |
| 1, HTTP 502 | Meta refused delivery | Usually the 24-hour window (below). Report it in the terminal. |
| 1, HTTP 403 | Secret wrong or missing | Check `$OMNI_NOTIFY_SECRET` and `~/.claude/.omni-notify-secret`. |
| 1, non-JSON body | The CDN blocked it, not the app | The app only ever answers JSON. Check the `User-Agent` header. |
| 2 | Empty message, or no secret configured | Fix and retry; nothing was sent. |

**The 24-hour window.** WhatsApp only lets a business number message someone who
messaged it in the last 24 hours. Go quiet for a day and the next send comes back
502 with Meta's error. That is WhatsApp policy, not a broken endpoint. The fix is
Mattia's: he sends any message to the number, which reopens the window. Tell him
that in the terminal — retrying will not help until he does.

## Configuration

- Secret: `$OMNI_NOTIFY_SECRET` if set, otherwise `~/.claude/.omni-notify-secret`.
  That file sits outside every checkout, so it cannot be committed by accident.
- Endpoint: `https://api.bedigital-omni.com/notify`, override with
  `$OMNI_NOTIFY_URL` or `--url`.
- `--dry-run` prints the exact JSON payload and sends nothing. Use it to check
  encoding without spending a message.
- Stdlib only — no venv, no `jq`, runs from any project.
