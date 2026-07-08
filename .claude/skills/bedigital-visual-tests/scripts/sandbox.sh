#!/usr/bin/env bash
# bedigital-visual-tests — deterministic Docker mechanics for the sandbox.
#
# Subcommands (run from the target repo root):
#   status   is this repo onboarded and is the base current?
#   doctor   static preflight: validate the recipe + rendered compose (no build)
#   onboard  build the base image (deps baked in), stamp the lockfile hash
#   up       spin a fresh, isolated sandbox from COMMITTED code; print its URL
#   reset    restore a clean seeded DB on the active sandbox (app stays up)
#   down     tear down the last run's sandbox
#   nuke     also drop the base image / stamp (force a re-onboard)
#
# The recipe lives in the target repo under .bedigital-visual-tests/:
#   recipe.env            (sourced below — see templates/recipe.env.example)
#   sandbox.compose.yml   (the sandbox definition / sanitizing override)
#   Dockerfile.base       (self-contained path only)
#   Dockerfile.sandbox    (self-contained path only; FROM ${BASE_IMAGE})
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # this skill's scripts/ dir
BVT_DIR=".bedigital-visual-tests"
RECIPE="$BVT_DIR/recipe.env"
STAMP="$BVT_DIR/.base.hash"       # gitignored; lockfile hash at last onboard
RUNS_DIR="$BVT_DIR/.runs"         # gitignored; one <run>.env per concurrent `up`
LAST_RUN="$BVT_DIR/.last-run"     # gitignored; back-compat pointer to newest run

die() { echo "ERROR: $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

require_repo() {
  git rev-parse --show-toplevel >/dev/null 2>&1 || die "not inside a git repository"
  [ -f "$RECIPE" ] || die "no recipe at $RECIPE — onboard this repo first (see reference/onboarding.md)"
}

load_recipe() {
  # Recipe contract (all relative to repo root):
  #   APP_SERVICE   compose service running the web app        (required)
  #   APP_PORT      container port the app listens on           (required)
  #   HEALTH_PATH   path polled on the published port for 200   (default /)
  #   LOCKFILES     space-separated lockfile globs for the hash (required)
  #   BASE_COMPOSE  repo compose to layer the override under    (optional)
  #   DATA_SERVICES stateful services `reset` recreates          (default postgres)
  #   MIGRATE_CMD   schema/migration slot, run via $COMPOSE       (optional)
  #   SEED_CMD      data-seed slot, run via $COMPOSE              (optional)
  #   RESET_RESTART_SERVICES services `reset` restarts in place  (default APP_SERVICE)
  #   RESET_CMD     full reseed OVERRIDE for `reset`             (optional escape hatch)
  # TRUST: this sources the target repo's committed recipe as SHELL on the HOST
  # (and MIGRATE_CMD/SEED_CMD/RESET_CMD run via `bash -c` on the host, though by
  # convention their bodies are `$COMPOSE run/exec …` so the work happens IN a
  # container) — NOT sandboxed in Docker.
  # Only run this skill on repositories you trust. See SKILL.md / onboarding.md.
  # shellcheck disable=SC1090
  source "$RECIPE"
  : "${APP_SERVICE:?recipe missing APP_SERVICE}"
  : "${APP_PORT:?recipe missing APP_PORT}"
  : "${LOCKFILES:?recipe missing LOCKFILES}"
  HEALTH_PATH="${HEALTH_PATH:-/}"
  BASE_COMPOSE="${BASE_COMPOSE:-}"
  DATA_SERVICES="${DATA_SERVICES:-postgres}"
  MIGRATE_CMD="${MIGRATE_CMD:-}"
  SEED_CMD="${SEED_CMD:-}"
  RESET_RESTART_SERVICES="${RESET_RESTART_SERVICES:-$APP_SERVICE}"
  RESET_CMD="${RESET_CMD:-}"
}

repo_slug() { basename "$(git rev-parse --show-toplevel)" | tr '[:upper:] ' '[:lower:]-'; }

lockfile_hash() {
  # Stable hash of all lockfile contents AS COMMITTED — each matched lockfile is
  # read from HEAD (git show), NOT the working tree, so an uncommitted lockfile
  # edit can't drift the base identity away from the committed app code the
  # sandbox actually builds. Drives base reuse + re-onboard detection.
  # LOCKFILES may contain globs, so expand it (word-split + pathname) to discover
  # paths; then read the committed blob for each.
  # shellcheck disable=SC2086
  local files; files=$(ls -1 $LOCKFILES 2>/dev/null | sort || true)
  [ -n "$files" ] || die "no lockfiles matched LOCKFILES=\"$LOCKFILES\""
  local f
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    git cat-file -e "HEAD:$f" 2>/dev/null \
      || die "lockfile '$f' is not committed at HEAD — commit it, then re-run"
  done <<< "$files"
  # Stream committed blobs (binary-safe: handles e.g. bun.lockb) into the hash.
  while IFS= read -r f; do [ -n "$f" ] && git show "HEAD:$f"; done <<< "$files" \
    | sha256sum | cut -c1-12
}

base_image() { echo "bdvt-$(repo_slug)-base:$(lockfile_hash)"; }

# Newest run-state file (per-run isolation for concurrent `up`s); falls back to
# the legacy single-file .last-run so pre-existing runs still tear down.
latest_run_file() {
  local f
  f=$(ls -1t "$RUNS_DIR"/*.env 2>/dev/null | head -n1 || true)
  if [ -n "$f" ]; then echo "$f"; elif [ -f "$LAST_RUN" ]; then echo "$LAST_RUN"; fi
}

# Check out committed HEAD into a detached worktree at $1 and overlay the
# (possibly uncommitted) recipe files. App code stays as-committed; only the
# recipe / Dockerfiles / .dockerignore are copied over so the recipe can be
# iterated without a commit. Caller owns removing the worktree.
prepare_head_worktree() {
  local wt="$1"
  git worktree add --detach --quiet "$wt" HEAD
  mkdir -p "$wt/$BVT_DIR"
  cp -f "$BVT_DIR"/recipe.env "$BVT_DIR"/sandbox.compose.yml "$wt/$BVT_DIR"/ 2>/dev/null || true
  [ -f "$BVT_DIR/Dockerfile.base" ]    && cp -f "$BVT_DIR/Dockerfile.base" "$wt/$BVT_DIR"/
  [ -f "$BVT_DIR/Dockerfile.sandbox" ] && cp -f "$BVT_DIR/Dockerfile.sandbox" "$wt/$BVT_DIR"/
  # Overlay an uncommitted build-context .dockerignore too (docs tell authors to
  # add one; the build context is the repo root, so it lives there).
  [ -f ".dockerignore" ] && cp -f ".dockerignore" "$wt/.dockerignore"
  return 0
}

# Assemble compose args. --project-directory pins the repo root as the project
# dir so relative build contexts/dockerfiles resolve against it — NOT against
# the .bedigital-visual-tests/ folder the override lives in (which would double
# the path). Callers cd to the repo root (or its HEAD worktree) first.
compose_files() {
  local args=(--project-directory .)
  [ -n "$BASE_COMPOSE" ] && args+=(-f "$BASE_COMPOSE")
  args+=(-f "$BVT_DIR/sandbox.compose.yml")
  printf '%s\n' "${args[@]}"
}

# ---- lifecycle helpers (shared by up + reset) ------------------------------
# Resolve the published host port of APP_SERVICE, parsed to just the port so an
# IPv6 bind (`[::]:32768`) or multiple bindings still reduce to the number.
# cd's into $wt so the relative compose paths resolve.
app_hostport() {  # args: proj wt
  local proj="$1" wt="$2"; local cf; mapfile -t cf < <(compose_files)
  ( cd "$wt" && docker compose -p "$proj" "${cf[@]}" port "$APP_SERVICE" "$APP_PORT" ) \
    | head -n1 | sed 's/.*://'
}

# Poll HEALTH_PATH on the published URL until it returns 200 (or times out).
# 0 = healthy. One source of truth for both `up` and post-`reset` gating.
wait_for_health() {  # args: url
  local url="$1" _
  for _ in $(seq 1 60); do
    curl -fsS -o /dev/null "${url}${HEALTH_PATH}" && return 0
    sleep 2
  done
  return 1
}

# Run a MIGRATE_CMD/SEED_CMD lifecycle slot with $COMPOSE and $PROJ in scope,
# exactly as the recipe author would type it — by convention `$COMPOSE run --rm
# <svc>` or `$COMPOSE exec -T <svc> …`, so the migrate/seed work runs INSIDE a
# container, not as host shell. No-op when the slot is empty.
# TRUST: like RESET_CMD, the slot string is the committed recipe executed on the
# host via `bash -c` — only run trusted repos (see load_recipe).
run_slot() {  # args: label proj wt run baseimg cmd
  local label="$1" proj="$2" wt="$3" run="$4" baseimg="$5" cmd="$6"
  [ -n "$cmd" ] || return 0
  local cf; mapfile -t cf < <(compose_files)
  echo ">> $label"
  ( cd "$wt" && BASE_IMAGE="$baseimg" BDVT_RUN="$run" \
      COMPOSE="docker compose -p $proj ${cf[*]}" PROJ="$proj" bash -c "$cmd" )
}

cmd_status() {
  require_repo; load_recipe
  local cur; cur=$(lockfile_hash)
  echo "repo:        $(repo_slug)"
  echo "recipe:      present ($RECIPE)"
  echo "lockfiles:   $LOCKFILES"
  echo "current hash: $cur"
  if [ -f "$STAMP" ]; then
    local stamped; stamped=$(cat "$STAMP")
    if [ "$stamped" = "$cur" ]; then
      echo "onboarded:   YES — base is current (hash $stamped). Fast path: run 'up'."
    else
      echo "onboarded:   STALE — deps changed (base $stamped != $cur). Run 'onboard' to rebuild."
    fi
  else
    echo "onboarded:   NO — never onboarded. Author the recipe, then run 'onboard'."
  fi
}

# Static preflight: validate the authored recipe + rendered compose WITHOUT
# building anything, so onboarding fails fast with concrete, framework-agnostic
# reasons instead of a slow build/health-gate timeout. Returns non-zero if any
# check FAILs (warnings don't fail). Also runnable standalone.
cmd_doctor() {
  require_repo; load_recipe
  local fails=0 warns=0
  _p(){ echo "  PASS  $*"; }
  _w(){ echo "  WARN  $*"; warns=$((warns+1)); }
  _f(){ echo "  FAIL  $*"; fails=$((fails+1)); }

  echo ">> doctor: $(repo_slug) — static recipe checks (no build)"
  _p "recipe vars: APP_SERVICE=$APP_SERVICE APP_PORT=$APP_PORT HEALTH_PATH=$HEALTH_PATH"

  # Lockfiles must be committed — the base identity is hashed from committed blobs.
  local any_lf=0 lf_bad=0 pat f
  for pat in $LOCKFILES; do
    for f in $(ls -1 $pat 2>/dev/null); do
      any_lf=1
      git cat-file -e "HEAD:$f" 2>/dev/null || { _f "lockfile not committed at HEAD: $f"; lf_bad=1; }
    done
  done
  [ "$any_lf" = 1 ] || _f "no files matched LOCKFILES=\"$LOCKFILES\""
  [ "$any_lf" = 1 ] && [ "$lf_bad" = 0 ] && _p "lockfiles committed: $LOCKFILES"

  # Compose assets present.
  [ -f "$BVT_DIR/sandbox.compose.yml" ] || _f "missing $BVT_DIR/sandbox.compose.yml"
  if [ -n "$BASE_COMPOSE" ]; then
    [ -f "$BASE_COMPOSE" ] && _p "BASE_COMPOSE exists: $BASE_COMPOSE" || _f "BASE_COMPOSE not found: $BASE_COMPOSE"
  fi
  if [ -f "$BVT_DIR/Dockerfile.base" ] || [ -f "$BVT_DIR/Dockerfile.sandbox" ]; then
    [ -f ".dockerignore" ] && _p ".dockerignore present (SHAPE B build context)" \
      || _w "no .dockerignore at repo root — SHAPE B may bake node_modules/.git/.env into the image"
  fi

  # Raw-file checks (pre-render): fixed container_name, and env_files that won't
  # exist in the committed HEAD-worktree build.
  local raw_files=("$BVT_DIR/sandbox.compose.yml"); [ -n "$BASE_COMPOSE" ] && raw_files=("$BASE_COMPOSE" "${raw_files[@]}")
  while IFS= read -r ln; do
    [ -n "$ln" ] && _w "fixed container_name breaks per-run isolation (template with \${BDVT_RUN}): ${ln#*:}"
  done < <(grep -nE '^[[:space:]]*container_name:' "${raw_files[@]}" 2>/dev/null | grep -v 'BDVT_RUN' || true)

  local ef
  while IFS= read -r ef; do
    [ -n "$ef" ] || continue
    ef="${ef%\"}"; ef="${ef#\"}"; ef="${ef%\'}"; ef="${ef#\'}"
    if git ls-files --error-unmatch "$ef" >/dev/null 2>&1; then
      _p "env_file committed: $ef"
    else
      _w "env_file '$ef' is not committed — it will be ABSENT in the HEAD-worktree build; commit a throwaway stub or move the vars inline into the sandbox compose"
    fi
  done < <(awk '
    /^[[:space:]]*env_file:[[:space:]]*[^[:space:]#].*/ { p=$0; sub(/^[^:]*:[[:space:]]*/,"",p); print p; next }
    /^[[:space:]]*env_file:[[:space:]]*$/ { blk=1; next }
    blk==1 && /^[[:space:]]*-[[:space:]]*/ { p=$0; sub(/^[[:space:]]*-[[:space:]]*/,"",p); sub(/[[:space:]]*#.*$/,"",p); print p; next }
    blk==1 { blk=0 }
  ' "${raw_files[@]}" 2>/dev/null || true)

  # Render the compose (with placeholder BASE_IMAGE/BDVT_RUN) and check services.
  local cf; mapfile -t cf < <(compose_files)
  local errf; errf=$(mktemp)
  if BASE_IMAGE="doctor" BDVT_RUN="doctor" docker compose "${cf[@]}" config >/dev/null 2>"$errf"; then
    _p "compose config renders (BASE_IMAGE/BDVT_RUN interpolate)"
    # List services with ALL profiles enabled — `config --services` hides
    # profile-gated services (e.g. one-shot migrate/seed) by default, which would
    # falsely flag a slot that targets them.
    local profs pr; profs=$(BASE_IMAGE="doctor" BDVT_RUN="doctor" docker compose "${cf[@]}" config --profiles 2>/dev/null)
    local prof_args=(); for pr in $profs; do prof_args+=(--profile "$pr"); done
    local svcs; svcs=$(BASE_IMAGE="doctor" BDVT_RUN="doctor" docker compose "${cf[@]}" ${prof_args[@]+"${prof_args[@]}"} config --services 2>/dev/null)
    grep -qx "$APP_SERVICE" <<<"$svcs" && _p "APP_SERVICE '$APP_SERVICE' is defined" \
      || _f "APP_SERVICE '$APP_SERVICE' is not a service (have: $(echo $svcs | tr '\n' ' '))"
    local ds; for ds in $DATA_SERVICES; do
      grep -qx "$ds" <<<"$svcs" || _w "DATA_SERVICES entry '$ds' is not a defined service"
    done
    # Slot commands should target a real service (heuristic: last token).
    local sc scv
    for sc in "MIGRATE_CMD:$MIGRATE_CMD" "SEED_CMD:$SEED_CMD"; do
      local lbl="${sc%%:*}" body="${sc#*:}"
      [ -n "$body" ] || continue
      scv=$(echo "$body" | grep -oE '(run[[:space:]]+(--rm[[:space:]]+)?(-{1,2}[A-Za-z-]+[[:space:]]+)*|exec[[:space:]]+(-{1,2}[A-Za-z-]+[[:space:]]+)*)[A-Za-z0-9_.-]+' | grep -oE '[A-Za-z0-9_.-]+$' | head -1)
      if [ -n "$scv" ]; then
        grep -qx "$scv" <<<"$svcs" && _p "$lbl targets service '$scv'" \
          || _w "$lbl references service '$scv' which is not defined in the compose"
      fi
    done
    # Deep structural checks (ports/bind-mounts/container_name) via node.
    if have node; then
      local jf ndf; jf=$(mktemp); ndf=$(mktemp)
      BASE_IMAGE="doctor" BDVT_RUN="doctor" docker compose "${cf[@]}" config --format json > "$jf" 2>/dev/null || true
      node "$SELF_DIR/doctor-compose.js" "$APP_SERVICE" "$APP_PORT" < "$jf" > "$ndf" 2>/dev/null || true
      while IFS= read -r line; do
        case "$line" in FAIL*) fails=$((fails+1));; WARN*) warns=$((warns+1));; esac
        [ -n "$line" ] && echo "  $line"
      done < "$ndf"
      rm -f "$jf" "$ndf"
    else
      _w "node not found — skipping deep port/bind-mount/container_name checks"
    fi
  else
    _f "compose config failed to render: $(head -1 "$errf")"
  fi
  rm -f "$errf"

  echo ""
  if [ "$fails" -eq 0 ]; then
    echo ">> doctor: OK — 0 failing, $warns warning(s)."
    return 0
  fi
  echo ">> doctor: $fails failing, $warns warning(s) — fix the FAILs before onboarding."
  return 1
}

cmd_onboard() {
  require_repo; load_recipe
  [ -f "$BVT_DIR/sandbox.compose.yml" ] || die "missing $BVT_DIR/sandbox.compose.yml"
  echo ">> Preflight (doctor)..."
  cmd_doctor || die "doctor found blocking issues — fix the FAILs, then re-run onboard"
  local img; img=$(base_image)   # also asserts lockfiles are committed
  echo ">> Onboarding $(repo_slug) — building base image (deps baked in). Slow, once."

  # Build from COMMITTED HEAD (a detached worktree), NOT the working tree — same
  # mechanism as 'up'. Otherwise dirty deps could bake a base whose packages !=
  # the committed lockfiles the hash/stamp are computed from.
  local wt; wt="$(git rev-parse --show-toplevel)/../.bdvt-worktrees/$(repo_slug)-onboard-$$"
  echo ">> Checking out committed HEAD into an isolated worktree..."
  prepare_head_worktree "$wt"

  local rc=0
  if [ -f "$BVT_DIR/Dockerfile.base" ]; then
    # Self-contained path: build the explicit base image, tagged by lockfile hash.
    ( cd "$wt" && DOCKER_BUILDKIT=1 docker build -f "$BVT_DIR/Dockerfile.base" -t "$img" . ) || rc=$?
  else
    # Reuse path: warm the repo's own build cache via the composed build.
    local cf; mapfile -t cf < <(compose_files)
    ( cd "$wt" && DOCKER_BUILDKIT=1 docker compose -p "bdvt-$(repo_slug)-onboard" "${cf[@]}" build ) || rc=$?
  fi
  git worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
  [ "$rc" -eq 0 ] || die "base build failed"

  lockfile_hash > "$STAMP"
  echo ">> Onboarded. Base stamped at hash $(cat "$STAMP"). Run 'up' to test."
}

cmd_up() {
  require_repo; load_recipe
  local cur; cur=$(lockfile_hash)
  [ -f "$STAMP" ] || die "not onboarded — run 'onboard' first"
  [ "$(cat "$STAMP")" = "$cur" ] || die "base is stale (deps changed) — run 'onboard' to rebuild"

  local slug run proj wt evid baseimg runfile up_ok=""
  slug=$(repo_slug)
  # Resolve the base image name+hash NOW, from the real repo — inside the HEAD
  # worktree the slug and lockfile hash would both differ (different toplevel,
  # CRLF-normalized checkout).
  baseimg=$(base_image)
  run="$(date +%Y%m%d-%H%M%S)-$$"
  proj="bdvt-$slug-$run"
  wt="$(git rev-parse --show-toplevel)/../.bdvt-worktrees/$slug-$run"
  evid="$(git rev-parse --show-toplevel)/$BVT_DIR/evidence/$run"
  runfile="$RUNS_DIR/$run.env"
  mkdir -p "$evid" "$RUNS_DIR"

  # Clean build of COMMITTED code: a detached worktree of HEAD as the build
  # context, with the (possibly uncommitted) recipe files overlaid.
  echo ">> Checking out committed HEAD into an isolated worktree..."
  prepare_head_worktree "$wt"

  # Per-run state so two concurrent `up`s don't clobber each other's control
  # plane. line1 project, line2 worktree, line3 run id (reset needs the run id to
  # re-interpolate ${BDVT_RUN} container names when recreating services).
  printf '%s\n%s\n%s\n' "$proj" "$wt" "$run" > "$runfile"
  printf '%s\n%s\n%s\n' "$proj" "$wt" "$run" > "$LAST_RUN"   # back-compat pointer

  local cf; mapfile -t cf < <(compose_files)

  # From here on, any failure before we print SANDBOX_URL leaves a half-built
  # sandbox + worktree + run-state; tear it all down. Cleared on success.
  trap 'if [ -z "$up_ok" ]; then
          echo "!! up failed — tearing down partial sandbox ($proj)" >&2
          ( cd "$wt" 2>/dev/null && docker compose -p "$proj" "${cf[@]}" down -v --remove-orphans ) >/dev/null 2>&1 || true
          git worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
          rm -f "$runfile"
          [ -f "$LAST_RUN" ] && [ "$(sed -n 1p "$LAST_RUN" 2>/dev/null)" = "$proj" ] && rm -f "$LAST_RUN"
        fi' EXIT

  echo ">> Spinning sandbox (project $proj, ephemeral port)..."
  # BDVT_RUN lets the override interpolate per-run-unique container names
  # (fixed container_name is global and breaks isolation — see gotchas.md).
  if [ -n "$MIGRATE_CMD" ] || [ -n "$SEED_CMD" ]; then
    # Data-backed app: build images, bring the DATA layer up HEALTHY first, then
    # run the migrate + seed slots BEFORE the app boots — so the app never starts
    # against an empty/unmigrated DB. (Apps that already encode this ordering in
    # compose via depends_on: service_completed_successfully just leave the slots
    # empty and fall through to the single `up` below.)
    (
      cd "$wt"
      export BASE_IMAGE="$baseimg" BDVT_RUN="$run" DOCKER_BUILDKIT=1
      docker compose -p "$proj" "${cf[@]}" build
      set -f
      # shellcheck disable=SC2086
      docker compose -p "$proj" "${cf[@]}" up -d --no-deps --wait $DATA_SERVICES
      set +f
    )
    run_slot "Running MIGRATE_CMD" "$proj" "$wt" "$run" "$baseimg" "$MIGRATE_CMD"
    run_slot "Running SEED_CMD"    "$proj" "$wt" "$run" "$baseimg" "$SEED_CMD"
  fi
  (
    cd "$wt"
    BASE_IMAGE="$baseimg" BDVT_RUN="$run" DOCKER_BUILDKIT=1 \
      docker compose -p "$proj" "${cf[@]}" up -d --build
  )

  # Ephemeral host port: the override maps "0:APP_PORT" so Docker picks a free one.
  local hostport url
  hostport=$(app_hostport "$proj" "$wt")
  [ -n "$hostport" ] || die "could not resolve published port for $APP_SERVICE:$APP_PORT"
  url="http://localhost:$hostport"

  echo ">> Waiting for health at ${url}${HEALTH_PATH} ..."
  if ! wait_for_health "$url"; then
    echo "!! App never became healthy. Recent logs:" >&2
    (cd "$wt" && docker compose -p "$proj" "${cf[@]}" logs --tail 40 "$APP_SERVICE") >&2 || true
    echo "   (Most common cause: missing secrets/env — see reference/gotchas.md)" >&2
    die "sandbox unhealthy"
  fi

  up_ok=1; trap - EXIT   # success — keep the sandbox; disarm the teardown trap
  echo ""
  echo "SANDBOX_URL=$url"
  echo "EVIDENCE_DIR=$evid"
  echo ">> Ready. Drive it with agent-browser (reference/driving-the-app.md); 'down' when done."
}

cmd_down() {
  require_repo; load_recipe
  local runfile; runfile=$(latest_run_file)
  [ -n "$runfile" ] && [ -f "$runfile" ] || { echo "no recorded run to tear down"; return 0; }
  local proj wt; proj=$(sed -n 1p "$runfile"); wt=$(sed -n 2p "$runfile")
  local cf; mapfile -t cf < <(compose_files)
  if [ -d "$wt" ]; then
    ( cd "$wt" && docker compose -p "$proj" "${cf[@]}" down -v --remove-orphans ) || true
    git worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
  else
    docker compose -p "$proj" down -v --remove-orphans 2>/dev/null || true
  fi
  rm -f "$runfile"
  # Clear the back-compat pointer if it named this same run.
  [ -f "$LAST_RUN" ] && [ "$(sed -n 1p "$LAST_RUN" 2>/dev/null)" = "$proj" ] && rm -f "$LAST_RUN"
  echo ">> Torn down $proj (base image kept)."
}

cmd_reset() {
  # Restore a clean, seeded DB between missions without rebuilding the sandbox.
  # Adversarial missions mutate state; this gives each one an identical slate.
  require_repo; load_recipe
  local runfile; runfile=$(latest_run_file)
  [ -n "$runfile" ] && [ -f "$runfile" ] || die "no active sandbox to reset — run 'up' first"
  local proj wt run; proj=$(sed -n 1p "$runfile"); wt=$(sed -n 2p "$runfile"); run=$(sed -n 3p "$runfile")
  [ -n "$run" ] || run="${proj#bdvt-$(repo_slug)-}"
  [ -d "$wt" ] || die "recorded worktree missing ($wt) — run 'up' again"
  local baseimg; baseimg=$(base_image)   # computed at repo root (correct slug/hash)
  local cf; mapfile -t cf < <(compose_files)
  echo ">> Resetting sandbox data (fresh seeded DB; app restarts in place)..."
  (
    cd "$wt"
    export BDVT_RUN="$run"
    if [ -n "$RESET_CMD" ]; then
      # ESCAPE HATCH: the recipe author owns the entire reseed lifecycle.
      # $COMPOSE and $PROJ are provided. When set, MIGRATE_CMD/SEED_CMD are NOT
      # auto-run here (RESET_CMD is expected to include them).
      COMPOSE="docker compose -p $proj ${cf[*]}" PROJ="$proj" bash -c "$RESET_CMD"
    else
      # Default lifecycle: recreate the data services + their anonymous volumes
      # (fresh empty DB), then re-run the migrate + seed slots below. This
      # replaces the old "the DB image's initdb re-seeds itself" assumption, which
      # is false for apps that seed via migrations/commands (Rails, Django,
      # FastAPI, Prisma …). --no-deps + --wait: recreate ONLY the data services
      # and block until they are healthy before migrate runs. DATA_SERVICES is
      # word-split (may be several services); `set -f` stops pathname expansion.
      set -f
      # shellcheck disable=SC2086
      docker compose -p "$proj" "${cf[@]}" rm -v -sf $DATA_SERVICES
      # shellcheck disable=SC2086
      docker compose -p "$proj" "${cf[@]}" up -d --no-deps --wait $DATA_SERVICES
      set +f
    fi
  )
  if [ -z "$RESET_CMD" ]; then
    run_slot "Running MIGRATE_CMD" "$proj" "$wt" "$run" "$baseimg" "$MIGRATE_CMD"
    run_slot "Running SEED_CMD"    "$proj" "$wt" "$run" "$baseimg" "$SEED_CMD"
  fi
  # Restart the app IN PLACE so it drops any stale DB pool / prepared statements
  # bound to the destroyed DB. `restart` keeps the existing container, so its
  # ephemeral host port (and the SANDBOX_URL already handed to the driver) is
  # preserved — unlike `up --force-recreate`, which would reassign the port.
  if [ -n "$RESET_RESTART_SERVICES" ]; then
    set -f
    # shellcheck disable=SC2086
    ( cd "$wt" && docker compose -p "$proj" "${cf[@]}" restart $RESET_RESTART_SERVICES ) || true
    set +f
  fi
  # Re-gate on health so the next mission never starts against a half-reset app.
  local hostport url
  hostport=$(app_hostport "$proj" "$wt")
  if [ -n "$hostport" ]; then
    url="http://localhost:$hostport"
    echo ">> Waiting for health at ${url}${HEALTH_PATH} ..."
    if ! wait_for_health "$url"; then
      echo "!! App not healthy after reset. Recent logs:" >&2
      (cd "$wt" && docker compose -p "$proj" "${cf[@]}" logs --tail 40 "$APP_SERVICE") >&2 || true
      die "reset left the sandbox unhealthy"
    fi
  fi
  echo ">> Reset done — data reseeded, app healthy."
}

cmd_nuke() {
  require_repo; load_recipe
  cmd_down || true
  local img; img=$(base_image)
  docker image rm "$img" 2>/dev/null || true
  rm -f "$STAMP"
  echo ">> Removed base image + stamp. Next run needs a fresh 'onboard'."
}

have docker || die "docker not found on PATH"
have git || die "git not found on PATH"
case "${1:-}" in
  status)  cmd_status ;;
  doctor)  cmd_doctor ;;
  onboard) cmd_onboard ;;
  up)      cmd_up ;;
  reset)   cmd_reset ;;
  down)    cmd_down ;;
  nuke)    cmd_nuke ;;
  *) echo "usage: sandbox.sh {status|doctor|onboard|up|reset|down|nuke}" >&2; exit 2 ;;
esac
