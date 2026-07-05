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


def _hardlink_tree(src_root, dst_root):
    """Recreate src_root at dst_root using hardlinks for files (near-instant,
    no content duplication) and real symlinks for symlinked entries (e.g.
    node_modules/.bin). Raises OSError on failure (e.g. cross-device);
    callers should discard the partial dst_root and fall back to a real
    install."""
    os.makedirs(dst_root, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(src_root):
        rel = os.path.relpath(dirpath, src_root)
        dst_dir = dst_root if rel == "." else os.path.join(dst_root, rel)
        os.makedirs(dst_dir, exist_ok=True)

        real_dirnames = []
        for name in dirnames:
            src_path = os.path.join(dirpath, name)
            if os.path.islink(src_path):
                os.symlink(os.readlink(src_path), os.path.join(dst_dir, name))
            else:
                real_dirnames.append(name)
        dirnames[:] = real_dirnames

        for name in filenames:
            src_path = os.path.join(dirpath, name)
            dst_path = os.path.join(dst_dir, name)
            if os.path.islink(src_path):
                os.symlink(os.readlink(src_path), dst_path)
            else:
                os.link(src_path, dst_path)


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
    """Fast-sync node_modules into `cwd` (a worker's worktree). Hardlinks
    node_modules from the linked project root when its package-lock.json is
    byte-identical to this one (near-instant); otherwise runs a real
    `npm ci` here. No-op if this isn't an npm project, or node_modules is
    already present (idempotent across resumed cycles)."""
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
            _hardlink_tree(src_modules, dst_modules)
            return f"linked node_modules from {root} (lockfile match)"
        except OSError:
            shutil.rmtree(dst_modules, ignore_errors=True)

    ok, msg = _npm_ci(cwd)
    if not ok:
        raise RuntimeError(msg)
    return msg
