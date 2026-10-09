#!/usr/bin/env bash
# Remote mode: run sandbox.sh on a Docker host over SSH and tunnel the app port back,
# so the browser stays on this machine. Called by sandbox.sh; not meant to be run directly.
#
# Opt-in per repo, from a USER-level file (never versioned):
#   ~/.config/esegui-test/remote.env
#     REMOTE=user@host            # SSH target with Docker, git and bash
#     REMOTE_REPOS="repo-a repo-b"  # repo directory names that use it
#
# Flow: bundle the committed HEAD -> unpack in ~/sandbox-qa/<repo> on the host -> overlay the
# local (possibly uncommitted) recipe files -> run the same sandbox.sh there -> for `up`,
# forward the published port to a free local port and rewrite SANDBOX_URL/EVIDENCE_DIR.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="${ESEGUI_REMOTE_CONF:-$HOME/.config/esegui-test/remote.env}"
# shellcheck disable=SC1090
source "$CONF"
: "${REMOTE:?remote.env missing REMOTE}"

die() { echo "ERROR: $*" >&2; exit 1; }
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=10 "$REMOTE")

top="$(git rev-parse --show-toplevel)"
slug="$(basename "$top" | tr '[:upper:] ' '[:lower:]-')"
rdir="sandbox-qa/$slug"
state="$HOME/.config/esegui-test/state"; mkdir -p "$state"
tunnel_pid="$state/$slug.tunnel"
cd "$top"

BVT_DIR=".esegui-test"; [ -d "$BVT_DIR" ] || BVT_DIR=".bedigital-visual-tests"

sync_to_remote() {
  "${SSH[@]}" true 2>/dev/null || die "cannot reach $REMOTE over SSH (laptop off or offline?). Not falling back to local: say so, or unset the repo in remote.env."
  local tmp; tmp="$(mktemp)"
  git bundle create "$tmp" HEAD 2>/dev/null
  "${SSH[@]}" "mkdir -p ~/sandbox-qa/_skill/scripts ~/$rdir && cd ~/$rdir && { [ -d .git ] || git init -q; }"
  "${SSH[@]}" "cat > ~/sandbox-qa/$slug.bundle" < "$tmp"; rm -f "$tmp"
  "${SSH[@]}" "cd ~/$rdir && git fetch -q ~/sandbox-qa/$slug.bundle '+HEAD:refs/esegui/head' && git checkout -q -f --detach refs/esegui/head"
  # Overlay the local recipe files (they may be uncommitted), same set sandbox.sh overlays.
  local f files=()
  for f in "$BVT_DIR/recipe.env" "$BVT_DIR/sandbox.compose.yml" "$BVT_DIR/Dockerfile.base" "$BVT_DIR/Dockerfile.sandbox" .dockerignore; do
    [ -f "$f" ] && files+=("$f")
  done
  if [ "${#files[@]}" -gt 0 ]; then
    tar -c "${files[@]}" | "${SSH[@]}" "cd ~/$rdir && tar -x"
  fi
  # The skill's scripts, with CRLF stripped in case they were checked out on Windows.
  local s
  for s in sandbox.sh doctor-compose.js; do
    sed 's/\r$//' "$SELF_DIR/$s" | "${SSH[@]}" "cat > ~/sandbox-qa/_skill/scripts/$s"
  done
}

run_remote() {  # args: subcommand
  "${SSH[@]}" "cd ~/$rdir && ESEGUI_ON_REMOTE=1 bash ~/sandbox-qa/_skill/scripts/sandbox.sh $1"
}

stop_tunnel() {
  if [ -f "$tunnel_pid" ]; then kill "$(cat "$tunnel_pid")" 2>/dev/null || true; rm -f "$tunnel_pid"; fi
}

free_local_port() {
  local p
  for _ in $(seq 1 50); do
    p=$((43000 + RANDOM % 2000))
    (echo > "/dev/tcp/127.0.0.1/$p") 2>/dev/null || { echo "$p"; return 0; }
  done
  die "no free local port for the tunnel"
}

cmd="${1:-}"
case "$cmd" in
  status|doctor|onboard|nuke)
    sync_to_remote; run_remote "$cmd" ;;
  up)
    sync_to_remote
    stop_tunnel
    out="$(mktemp)"
    run_remote up | tee "$out" >&2 || { rm -f "$out"; exit 1; }
    rurl="$(sed -n 's/^SANDBOX_URL=//p' "$out" | tail -1)"; rport="${rurl##*:}"
    revid="$(sed -n 's/^EVIDENCE_DIR=//p' "$out" | tail -1)"
    lport="$(free_local_port)"
    nohup ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes -L "127.0.0.1:$lport:127.0.0.1:$rport" "$REMOTE" >/dev/null 2>&1 &
    echo $! > "$tunnel_pid"; disown 2>/dev/null || true
    for _ in $(seq 1 20); do (echo > "/dev/tcp/127.0.0.1/$lport") 2>/dev/null && break; sleep 0.5; done
    levid="$top/$BVT_DIR/evidence/$(basename "$revid")"; mkdir -p "$levid"
    echo ""
    echo "SANDBOX_URL=http://localhost:$lport"
    echo "EVIDENCE_DIR=$levid"
    grep -E '^(TEST_USER|TEST_PASSWORD|LOGIN_PATH|POST_LOGIN_PATH)=' "$out" || true
    echo ">> Remote sandbox on $REMOTE, tunnelled to localhost:$lport. 'down' when done."
    rm -f "$out" ;;
  reset)
    run_remote reset ;;
  down)
    run_remote down || true; stop_tunnel ;;
  *) die "usage: remote.sh {status|doctor|onboard|up|reset|down|nuke}" ;;
esac
