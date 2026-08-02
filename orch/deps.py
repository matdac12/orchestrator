import filecmp
import os
import shutil
import subprocess

from orch import db

LOCKFILE = "package-lock.json"
DEPS_DIR = "node_modules"
# Never descend into these while looking for npm projects: a dependency's own
# lockfile isn't a project of ours, and .git holds no installable package.
PRUNE_DIRS = {DEPS_DIR, ".git"}


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


def _find_projects(cwd):
    """Every npm project under `cwd`, as paths relative to it ("." for the
    top level). A repo may hold several — tooling deps at the root plus the
    real app in `app/`, or a package per workspace — and each needs its own
    node_modules, so syncing only the top level leaves the worktree
    unbuildable."""
    found = []
    for dirpath, dirnames, filenames in os.walk(cwd):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        if LOCKFILE in filenames:
            found.append(os.path.relpath(dirpath, cwd))
    return sorted(found)


def _sync_one(root, cwd, rel):
    """Sync a single npm project, `rel` being its path relative to both the
    worktree `cwd` and the project `root`. Returns a status line; raises
    RuntimeError if the fallback install fails."""
    label = "root" if rel == os.curdir else rel.replace(os.sep, "/")
    dst_dir = os.path.normpath(os.path.join(cwd, rel))

    dst_modules = os.path.join(dst_dir, DEPS_DIR)
    if os.path.isdir(dst_modules):
        return f"{label}: node_modules already present"

    if root:
        src_dir = os.path.normpath(os.path.join(root, rel))
        src_lock = os.path.join(src_dir, LOCKFILE)
        src_modules = os.path.join(src_dir, DEPS_DIR)
        if (os.path.isfile(src_lock) and os.path.isdir(src_modules)
                and _same_file(src_lock, os.path.join(dst_dir, LOCKFILE))):
            try:
                _copy_tree(src_modules, dst_modules)
                return f"{label}: copied node_modules from {src_dir}"
            except (OSError, shutil.Error):
                shutil.rmtree(dst_modules, ignore_errors=True)

    ok, msg = _npm_ci(dst_dir)
    if not ok:
        raise RuntimeError(f"{label}: {msg}")
    return f"{label}: {msg}"


def sync(conn, project_name, cwd=None):
    """Fast-sync node_modules into `cwd` (a worker's worktree). Handles every
    npm project in the tree, not just the top level — `package.json` often
    lives in `app/` or one package per workspace, and a worktree missing
    those node_modules can't build or test. For each, copies node_modules
    from the matching directory of the linked project root when the two
    package-lock.json files are byte-identical (no network, no reinstall —
    just a local file copy, fully independent of the root so nothing written
    into it later can corrupt the shared root or any other worktree);
    otherwise runs a real `npm ci` there. No-op if this isn't an npm project,
    and per project if its node_modules is already present (idempotent
    across resumed cycles). A project that fails to install doesn't stop the
    others; the error at the end names every project and its outcome."""
    cwd = cwd or os.getcwd()
    proj = db.require_project(conn, project_name)
    root = proj["path"]

    projects = _find_projects(cwd)
    if not projects:
        return "no package-lock.json here; nothing to sync"

    if root and _norm(cwd) == _norm(root):
        return "already at the project root; nothing to sync"

    results = []
    failures = []
    for rel in projects:
        try:
            results.append(_sync_one(root, cwd, rel))
        except RuntimeError as e:
            failures.append(str(e))
            results.append(str(e))

    summary = "; ".join(results)
    if failures:
        raise RuntimeError(summary)
    return summary
