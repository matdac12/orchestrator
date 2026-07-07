#!/usr/bin/env bash
# bedigital-visual-tests — deterministic Docker mechanics for the sandbox.
#
# Subcommands (run from the target repo root):
#   status   is this repo onboarded and is the base current?
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
  #   RESET_CMD     custom reseed command for `reset`            (optional; SHAPE A)
  # TRUST: this sources the target repo's committed recipe as SHELL on the HOST
  # (and RESET_CMD runs via `bash -c` on the host) — NOT sandboxed in Docker.
  # Only run this skill on repositories you trust. See SKILL.md / onboarding.md.
  # shellcheck disable=SC1090
  source "$RECIPE"
  : "${APP_SERVICE:?recipe missing APP_SERVICE}"
  : "${APP_PORT:?recipe missing APP_PORT}"
  : "${LOCKFILES:?recipe missing LOCKFILES}"
  HEALTH_PATH="${HEALTH_PATH:-/}"
  BASE_COMPOSE="${BASE_COMPOSE:-}"
  DATA_SERVICES="${DATA_SERVICES:-postgres}"
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

cmd_onboard() {
  require_repo; load_recipe
  [ -f "$BVT_DIR/sandbox.compose.yml" ] || die "missing $BVT_DIR/sandbox.compose.yml"
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
  (
    cd "$wt"
    # BDVT_RUN lets the override interpolate per-run-unique container names
    # (fixed container_name is global and breaks isolation — see gotchas.md).
    BASE_IMAGE="$baseimg" BDVT_RUN="$run" DOCKER_BUILDKIT=1 \
      docker compose -p "$proj" "${cf[@]}" up -d --build
  )

  # Ephemeral host port: the override maps "0:APP_PORT" so Docker picks a free
  # one. Take the FIRST binding line, then the port after the LAST colon so an
  # IPv6 bind (`[::]:32768`) or multiple bindings still parse to just the port.
  local hostport url
  hostport=$( (cd "$wt" && docker compose -p "$proj" "${cf[@]}" port "$APP_SERVICE" "$APP_PORT") | head -n1 | sed 's/.*://')
  [ -n "$hostport" ] || die "could not resolve published port for $APP_SERVICE:$APP_PORT"
  url="http://localhost:$hostport"

  echo ">> Waiting for health at ${url}${HEALTH_PATH} ..."
  local ok=""
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "${url}${HEALTH_PATH}"; then ok=1; break; fi
    sleep 2
  done
  if [ -z "$ok" ]; then
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
  local cf; mapfile -t cf < <(compose_files)
  echo ">> Resetting sandbox data (fresh seeded DB; app stays up)..."
  (
    cd "$wt"
    export BDVT_RUN="$run"
    if [ -n "$RESET_CMD" ]; then
      # SHAPE A / custom: recipe author's reseed command. $COMPOSE and $PROJ are
      # provided; e.g. RESET_CMD='$COMPOSE --profile seed run --rm seed'
      COMPOSE="docker compose -p $proj ${cf[*]}" PROJ="$proj" bash -c "$RESET_CMD"
    else
      # Default (SHAPE B): drop the data services + their anonymous volumes so the
      # image's initdb/seed re-runs on recreate. --no-deps so compose does NOT
      # touch the app container — restarting/recreating it would reassign its
      # ephemeral host port and invalidate the SANDBOX_URL already in use. The app
      # reconnects lazily on its next query (its connection pool must tolerate a
      # dropped DB — a production-grade pool does; see gotchas.md).
      # DATA_SERVICES is intentionally word-split (multiple services); `set -f`
      # keeps a name from being pathname-expanded against the cwd.
      set -f
      # shellcheck disable=SC2086
      docker compose -p "$proj" "${cf[@]}" rm -v -sf $DATA_SERVICES
      # shellcheck disable=SC2086
      docker compose -p "$proj" "${cf[@]}" up -d --no-deps $DATA_SERVICES
      set +f
    fi
  )
  echo ">> Reset done — DB reseeded."
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
  onboard) cmd_onboard ;;
  up)      cmd_up ;;
  reset)   cmd_reset ;;
  down)    cmd_down ;;
  nuke)    cmd_nuke ;;
  *) echo "usage: sandbox.sh {status|onboard|up|reset|down|nuke}" >&2; exit 2 ;;
esac
