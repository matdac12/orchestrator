import filecmp
import os
import shutil
import subprocess

from orch import db

LOCKFILE = "package-lock.json"
DEPS_DIR = "node_modules"


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def _same_file(a, b):
    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def _copy_tree(src_root, dst_root):
    """Recreate src_root at dst_root as a fully independent copy — no shared
    inodes with the source, so nothing written into dst_root's files can
    ever affect src_root's (the reason this isn't a hardlink: some tools,
    e.g. `prisma generate` or `patch-package`, write into existing files
    inside node_modules rather than replacing them). Raises OSError or
    shutil.Error on failure; callers should discard the partial dst_root
    and fall back to a real install."""
    shutil.copytree(src_root, dst_root, symlinks=True)


def _npm_ci(cwd):
    npm = shutil.which("npm")
    if not npm:
        return False, "npm not found on PATH"
    try:
        result = subprocess.run(
            [npm, "ci"], cwd=cwd, capture_output=True, text=True,
            timeout=600)
    except Exception as e:
        return False, f"npm ci failed to start: {e}"
    if result.returncode != 0:
        return False, f"npm ci failed:\n{result.stderr.strip()}"
    return True, "npm ci completed"


def sync(conn, project_name, cwd=None):
    """Fast-sync node_modules into `cwd` (a worker's worktree). Copies
    node_modules from the linked project root when its package-lock.json is
    byte-identical to this one (no network, no reinstall — just a local
    file copy, fully independent of the root so nothing written into it
    later can corrupt the shared root or any other worktree); otherwise
    runs a real `npm ci` here. No-op if this isn't an npm project, or
    node_modules is already present (idempotent across resumed cycles)."""
    cwd = cwd or os.getcwd()
    proj = db.require_project(conn, project_name)
    root = proj["path"]

    dst_lock = os.path.join(cwd, LOCKFILE)
    if not os.path.isfile(dst_lock):
        return "no package-lock.json here; nothing to sync"

    dst_modules = os.path.join(cwd, DEPS_DIR)
    if os.path.isdir(dst_modules):
        return "node_modules already present; nothing to sync"

    if not root:
        ok, msg = _npm_ci(cwd)
        if not ok:
            raise RuntimeError(msg)
        return msg

    if _norm(cwd) == _norm(root):
        return "already at the project root; nothing to sync"

    src_lock = os.path.join(root, LOCKFILE)
    src_modules = os.path.join(root, DEPS_DIR)
    can_link = (os.path.isfile(src_lock) and os.path.isdir(src_modules)
                and _same_file(src_lock, dst_lock))

    if can_link:
        try:
            _copy_tree(src_modules, dst_modules)
            return f"copied node_modules from {root} (lockfile match)"
        except (OSError, shutil.Error):
            shutil.rmtree(dst_modules, ignore_errors=True)

    ok, msg = _npm_ci(cwd)
    if not ok:
        raise RuntimeError(msg)
    return msg
