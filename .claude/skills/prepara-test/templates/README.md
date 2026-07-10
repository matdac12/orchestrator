# Templates — recipes with blanks

Onboard by the **web surface** (see `reference/onboarding.md` §1), not by which
config files exist. Pick the shape, copy its files into the target repo's
`.bedigital-visual-tests/`, fill every `<...>`, then run `sandbox.sh doctor` →
`sandbox.sh onboard`.

| Shape | Use when | Start from |
|-------|----------|------------|
| `single-web-no-db` | one static/SSR app, no database (SPA, static server, lone SSR app) | `sandbox.compose.example.yml` (SHAPE B) — drop the DB/migrate/seed services; just build the app and publish `"0:<port>"` |
| `single-web-db` | one app server + a DB it migrates/seeds (Rails, Django, Laravel, FastAPI, Next-with-DB) | `single-web-db/` |
| `split-web-api-db` | separate frontend + backend that must be **one origin** (auth cookies / CORS / build-time public API URL) | `split-web-api-db/` |
| `existing-compose-override` | the repo's own compose already serves the full browser surface | `recipe.env.example` + `sandbox.compose.example.yml` (SHAPE A override); set `BASE_COMPOSE` |

These are **fill-in-the-blanks scaffolds, not runnable apps** — they encode the
two mechanics people get wrong (migrate/seed ordering; a same-origin proxy for
split stacks). `recipe.env.example` documents every recipe field in full;
`sandbox.compose.example.yml` shows the SHAPE A / SHAPE B compose patterns.
`doctor` will tell you what's still wrong before the slow build.
