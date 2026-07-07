#!/usr/bin/env bash
# bedigital-visual-tests — deterministic Docker mechanics for the sandbox.
#
# Subcommands (run from the target repo root):
#   status   is this repo onboarded and is the base current?
#   onboard  build the base image (deps baked in), stamp the lockfile hash
#   up       spin a fresh, isolated sandbox from COMMITTED code; print its URL
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
LAST_RUN="$BVT_DIR/.last-run"     # gitignored; PROJECT + WORKTREE of last `up`

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
  # shellcheck disable=SC1090
  source "$RECIPE"
  : "${APP_SERVICE:?recipe missing APP_SERVICE}"
  : "${APP_PORT:?recipe missing APP_PORT}"
  : "${LOCKFILES:?recipe missing LOCKFILES}"
  HEALTH_PATH="${HEALTH_PATH:-/}"
  BASE_COMPOSE="${BASE_COMPOSE:-}"
}

repo_slug() { basename "$(git rev-parse --show-toplevel)" | tr '[:upper:] ' '[:lower:]-'; }

lockfile_hash() {
  # Stable hash of all lockfile contents; drives base reuse + re-onboard detection.
  # shellcheck disable=SC2086
  local files; files=$(ls -1 $LOCKFILES 2>/dev/null | sort || true)
  [ -n "$files" ] || die "no lockfiles matched LOCKFILES=\"$LOCKFILES\""
  # shellcheck disable=SC2086
  cat $files | sha256sum | cut -c1-12
}

base_image() { echo "bdvt-$(repo_slug)-base:$(lockfile_hash)"; }

# Assemble the -f arguments: optional base compose, then our override.
compose_files() {
  local args=()
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
  local img; img=$(base_image)
  echo ">> Onboarding $(repo_slug) — building base image (deps baked in). Slow, once."
  if [ -f "$BVT_DIR/Dockerfile.base" ]; then
    # Self-contained path: build the explicit base image, tagged by lockfile hash.
    DOCKER_BUILDKIT=1 docker build -f "$BVT_DIR/Dockerfile.base" -t "$img" .
  else
    # Reuse path: warm the repo's own build cache via the composed build.
    local cf; mapfile -t cf < <(compose_files)
    DOCKER_BUILDKIT=1 docker compose -p "bdvt-$(repo_slug)-onboard" "${cf[@]}" build
  fi
  lockfile_hash > "$STAMP"
  echo ">> Onboarded. Base stamped at hash $(cat "$STAMP"). Run 'up' to test."
}

cmd_up() {
  require_repo; load_recipe
  local cur; cur=$(lockfile_hash)
  [ -f "$STAMP" ] || die "not onboarded — run 'onboard' first"
  [ "$(cat "$STAMP")" = "$cur" ] || die "base is stale (deps changed) — run 'onboard' to rebuild"

  local slug run proj wt evid
  slug=$(repo_slug)
  run="$(date +%Y%m%d-%H%M%S)-$$"
  proj="bdvt-$slug-$run"
  wt="$(git rev-parse --show-toplevel)/../.bdvt-worktrees/$slug-$run"
  evid="$(git rev-parse --show-toplevel)/$BVT_DIR/evidence/$run"
  mkdir -p "$evid"

  # Clean build of COMMITTED code: a detached worktree of HEAD as the build context.
  echo ">> Checking out committed HEAD into an isolated worktree..."
  git worktree add --detach --quiet "$wt" HEAD
  # Let the recipe iterate without a commit: copy the (possibly uncommitted)
  # recipe files over the committed app code. App code stays as-committed.
  mkdir -p "$wt/$BVT_DIR"
  cp -f "$BVT_DIR"/recipe.env "$BVT_DIR"/sandbox.compose.yml "$wt/$BVT_DIR"/ 2>/dev/null || true
  [ -f "$BVT_DIR/Dockerfile.base" ]    && cp -f "$BVT_DIR/Dockerfile.base" "$wt/$BVT_DIR"/
  [ -f "$BVT_DIR/Dockerfile.sandbox" ] && cp -f "$BVT_DIR/Dockerfile.sandbox" "$wt/$BVT_DIR"/

  echo "$proj"$'\n'"$wt" > "$LAST_RUN"

  local cf; mapfile -t cf < <(compose_files)
  echo ">> Spinning sandbox (project $proj, ephemeral port)..."
  (
    cd "$wt"
    # BDVT_RUN lets the override interpolate per-run-unique container names
    # (fixed container_name is global and breaks isolation — see gotchas.md).
    BASE_IMAGE="$(base_image)" BDVT_RUN="$run" DOCKER_BUILDKIT=1 \
      docker compose -p "$proj" "${cf[@]}" up -d --build
  )

  # Ephemeral host port: the override maps "0:APP_PORT" so Docker picks a free one.
  local hostport url
  hostport=$( (cd "$wt" && docker compose -p "$proj" "${cf[@]}" port "$APP_SERVICE" "$APP_PORT") | sed 's/.*://')
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

  echo ""
  echo "SANDBOX_URL=$url"
  echo "EVIDENCE_DIR=$evid"
  echo ">> Ready. Drive it with agent-browser (reference/driving-the-app.md); 'down' when done."
}

cmd_down() {
  require_repo; load_recipe
  [ -f "$LAST_RUN" ] || { echo "no recorded run to tear down"; return 0; }
  local proj wt; proj=$(sed -n 1p "$LAST_RUN"); wt=$(sed -n 2p "$LAST_RUN")
  local cf; mapfile -t cf < <(compose_files)
  if [ -d "$wt" ]; then
    ( cd "$wt" && docker compose -p "$proj" "${cf[@]}" down -v --remove-orphans ) || true
    git worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
  else
    docker compose -p "$proj" down -v --remove-orphans 2>/dev/null || true
  fi
  rm -f "$LAST_RUN"
  echo ">> Torn down $proj (base image kept)."
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
  down)    cmd_down ;;
  nuke)    cmd_nuke ;;
  *) echo "usage: sandbox.sh {status|onboard|up|down|nuke}" >&2; exit 2 ;;
esac
