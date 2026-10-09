# Templates: recipes with blanks

Pick the shape from the **web surface** (`reference/onboarding.md` §1), copy its files into the target repo's `.esegui-test/`, fill every `<...>`, then `sandbox.sh doctor` → `onboard`.

| Shape | Use when | Start from |
|-------|----------|------------|
| `single-web-no-db` | one app, no database (SPA, static server, lone SSR) | `sandbox.compose.example.yml` (SHAPE B); drop the DB/seed services |
| `single-web-db` | one app + a DB it migrates/seeds | `single-web-db/` |
| `split-web-api-db` | separate frontend + backend that must be **one origin** | `split-web-api-db/` |
| `existing-compose-override` | the repo's compose already serves the full surface | `recipe.env.example` + `sandbox.compose.example.yml` (SHAPE A); set `BASE_COMPOSE` |

Scaffolds, not runnable apps: they encode the two mechanics people get wrong (migrate/seed ordering; a same-origin proxy for split stacks). `recipe.env.example` documents every key; `doctor` reports what's still wrong before the slow build.
