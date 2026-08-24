#!/usr/bin/env python3
"""
GitHub auto-sync that will not revert main to an old checkout.

The old behaviour uploaded every local file that differed from GitHub. A stale
Replit (or PC) tree with Qubic URLs then overwrote authenticateCustomer / sbsports
on main every few minutes.

This script is **manual only**. Do not wire it back into `.replit` workflows or
`scripts/post-merge.sh`. If you run it, GitHub wins when ahead and Qubic-over-sbsports
uploads are refused.

Rules:
  1. Only run pushes while on `main`. Feature-branch / cloud-agent checkouts skip.
  2. If GitHub is ahead or histories diverged, PULL those files — do not upload.
  3. Never upload a file that would replace cloud BetBCK URLs with Qubic paths,
     or a Helper manifest older than the one already on GitHub. Repair local instead.
  4. Upload only when this clone is at or ahead of origin/main (real local edits).
"""

import os
import base64
import hashlib
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

GITHUB_OWNER = "NDGopher"
GITHUB_REPO = "UnifiedBetting"
GITHUB_BRANCH = "main"
REPO_ROOT = Path(__file__).resolve().parent.parent

EXTRA_SKIP_PREFIXES = (
    ".local/",
    ".git/",
    "attached_assets/",
    "frontend/node_modules/",
    "frontend/build/",
    "backend/__pycache__/",
    "backend/data/",
    "data/",
    "backend/logs/",
    "backend/betbck_html_logs/",
)

# Local content that must never overwrite a cloud/sbsports remote file.
STALE_MARKERS = (
    b"Qubic/SecurityPage.php",
    b"Qubic/StraightSportSelection.php",
    b"Qubic/PlayerGameSelection.php",
)
FRESH_MARKERS = (
    b"authenticateCustomer",
    b"sbsports.html",
    b"Get_LeagueLines2",
    b"Get_SportsLeagues",
)

DAEMON_INTERVAL_SECONDS = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [github-sync] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("github-sync")


def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def looks_like_stale_betbck(content: bytes) -> bool:
    return any(marker in content for marker in STALE_MARKERS)


def looks_like_cloud_betbck(content: bytes) -> bool:
    return any(marker in content for marker in FRESH_MARKERS)


def manifest_version(content: bytes):
    try:
        data = json.loads(content.decode("utf-8"))
        parts = str(data.get("version") or "0").split(".")
        return tuple(int(p) for p in (parts + ["0", "0", "0"])[:3])
    except Exception:
        return (0, 0, 0)


def is_stale_regression(rel_path: str, local: bytes, remote: bytes) -> bool:
    """True when uploading local would roll GitHub back to the old BetBCK stack."""
    if not remote:
        return False
    if looks_like_stale_betbck(local) and looks_like_cloud_betbck(remote):
        return True
    if rel_path.replace("\\", "/").endswith("betbck_extension/manifest.json"):
        if manifest_version(local) < manifest_version(remote):
            return True
    return False


def git_output(*args: str, check=True) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=str(REPO_ROOT),
        text=True,
        timeout=30,
        stderr=subprocess.DEVNULL if not check else None,
    ).strip()


def git_run(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        text=True,
        timeout=timeout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def current_branch() -> str:
    try:
        return git_output("rev-parse", "--abbrev-ref", "HEAD")
    except Exception:
        return ""


def local_head() -> str:
    try:
        return git_output("rev-parse", "HEAD")
    except Exception:
        return ""


def have_commit(sha: str) -> bool:
    if not sha:
        return False
    return git_run("cat-file", "-e", sha).returncode == 0


def is_ancestor(maybe_ancestor: str, maybe_descendant: str) -> bool:
    if not maybe_ancestor or not maybe_descendant:
        return False
    if not have_commit(maybe_ancestor) or not have_commit(maybe_descendant):
        return False
    return git_run("merge-base", "--is-ancestor", maybe_ancestor, maybe_descendant).returncode == 0


def relation_to_remote(local_sha: str, remote_sha: str) -> str:
    if not remote_sha:
        return "unknown"
    if local_sha == remote_sha:
        return "equal"
    if not have_commit(remote_sha):
        # GitHub has a commit this clone never fetched — treat as behind.
        return "behind"
    if is_ancestor(local_sha, remote_sha):
        return "behind"
    if is_ancestor(remote_sha, local_sha):
        return "ahead"
    return "diverged"


def api_request(method: str, path: str, body: dict = None):
    import urllib.error
    import urllib.request

    token = os.environ.get("GITHUB_TOKEN", "")
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        logger.error("API %s %s → %s: %s", method, path, e.code, body_text[:200])
        return None
    except Exception as exc:
        logger.error("API error %s %s: %s", method, path, exc)
        return None


def try_fast_forward() -> bool:
    """When this clone is a clean ancestor of GitHub main, pull with git."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return False
    url = f"https://x-access-token:{token}@github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git"
    fetch = git_run(
        "fetch",
        url,
        f"+refs/heads/{GITHUB_BRANCH}:refs/remotes/origin/{GITHUB_BRANCH}",
        timeout=120,
    )
    if fetch.returncode != 0:
        logger.warning("git fetch failed: %s", (fetch.stderr or "")[-300:])
        return False
    merge = git_run("merge", "--ff-only", f"origin/{GITHUB_BRANCH}")
    if merge.returncode != 0:
        logger.info("ff-only merge not possible (dirty or diverged tree).")
        return False
    logger.info("Fast-forwarded to origin/%s", GITHUB_BRANCH)
    return True


def get_remote_head_sha() -> str:
    result = api_request("GET", f"commits/{GITHUB_BRANCH}")
    if not result:
        return ""
    return str(result.get("sha") or "")


def get_remote_tree() -> dict:
    result = api_request("GET", f"git/trees/{GITHUB_BRANCH}?recursive=1")
    if not result:
        return {}
    return {
        item["path"]: item["sha"]
        for item in result.get("tree", [])
        if item["type"] == "blob"
    }


def get_remote_file_bytes(rel_path: str):
    result = api_request("GET", f"contents/{rel_path}?ref={GITHUB_BRANCH}")
    if not result:
        return None
    content = result.get("content")
    if not content:
        return None
    try:
        return base64.b64decode(content)
    except Exception:
        return None


def get_tracked_files() -> list:
    try:
        out = subprocess.check_output(
            ["git", "ls-files"], cwd=str(REPO_ROOT), text=True, timeout=15
        )
        files = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            if any(line.startswith(pfx) for pfx in EXTRA_SKIP_PREFIXES):
                continue
            files.append(line)
        return files
    except Exception as exc:
        logger.error("git ls-files failed: %s", exc)
        return []


def write_local_file(rel_path: str, content: bytes) -> bool:
    abs_path = REPO_ROOT / rel_path
    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(content)
        return True
    except Exception as exc:
        logger.error("Failed to write %s: %s", rel_path, exc)
        return False


def pull_file_from_github(rel_path: str) -> bool:
    remote = get_remote_file_bytes(rel_path)
    if remote is None:
        logger.error("Could not download %s from GitHub", rel_path)
        return False
    if write_local_file(rel_path, remote):
        logger.info("pulled: %s", rel_path)
        return True
    return False


def upload_file(rel_path: str, content: bytes, remote_sha: str, dry_run: bool) -> bool:
    if dry_run:
        logger.info("dry-run upload: %s", rel_path)
        return True
    body = {
        "message": f"auto-sync: {rel_path}",
        "content": base64.b64encode(content).decode(),
        "branch": GITHUB_BRANCH,
    }
    if remote_sha:
        body["sha"] = remote_sha
    if api_request("PUT", f"contents/{rel_path}", body):
        return True
    logger.error("Failed: %s", rel_path)
    return False


def sync_once(dry_run: bool = False):
    """Run a single sync cycle. Returns (uploaded, pulled, skipped)."""
    logger.info("Starting sync cycle...")

    branch = current_branch()
    if branch and branch != GITHUB_BRANCH:
        logger.info(
            "On branch %s, not %s — skip auto-sync so feature work cannot overwrite main.",
            branch,
            GITHUB_BRANCH,
        )
        return 0, 0, 0

    remote_head = get_remote_head_sha()
    local = local_head()
    rel = relation_to_remote(local, remote_head)
    logger.info("Git relation to origin/%s: %s (local=%s remote=%s)", GITHUB_BRANCH, rel, local[:10], remote_head[:10])

    if rel == "behind" and not dry_run:
        if try_fast_forward():
            logger.info("Local main fast-forwarded to GitHub. No uploads this cycle.")
            return 0, 1, 0
        logger.info("Fast-forward failed; updating mismatched files from GitHub instead.")

    remote_tree = get_remote_tree()
    tracked = get_tracked_files()
    if not tracked:
        logger.warning("No tracked files found.")
        return 0, 0, 0

    allow_upload = rel in ("equal", "ahead")
    if rel in ("behind", "diverged", "unknown"):
        logger.info(
            "GitHub is source of truth this cycle (%s). Updating local files; not uploading.",
            rel,
        )

    uploaded = 0
    pulled = 0
    skipped = 0

    for rel_path in tracked:
        abs_path = REPO_ROOT / rel_path
        if not abs_path.is_file():
            continue
        try:
            content = abs_path.read_bytes()
        except Exception:
            continue

        local_sha = git_blob_sha(content)
        remote_sha = remote_tree.get(rel_path)
        if local_sha == remote_sha:
            skipped += 1
            continue

        remote_bytes = None
        if remote_sha:
            remote_bytes = get_remote_file_bytes(rel_path)

        if remote_bytes is not None and is_stale_regression(rel_path, content, remote_bytes):
            logger.warning(
                "Refusing to push stale %s (would revert cloud BetBCK URLs / Helper). Pulling GitHub copy.",
                rel_path,
            )
            if not dry_run:
                write_local_file(rel_path, remote_bytes)
            pulled += 1
            continue

        if not allow_upload:
            if remote_bytes is None:
                skipped += 1
                continue
            if dry_run:
                logger.info("dry-run pull: %s", rel_path)
            else:
                write_local_file(rel_path, remote_bytes)
                logger.info("pulled: %s", rel_path)
            pulled += 1
            continue

        action = "create" if remote_sha is None else "update"
        logger.info("%s: %s", action, rel_path)
        if upload_file(rel_path, content, remote_sha, dry_run):
            uploaded += 1
            if not dry_run:
                time.sleep(0.3)

    logger.info(
        "Done: %d uploaded, %d pulled from GitHub, %d unchanged.",
        uploaded,
        pulled,
        skipped,
    )
    return uploaded, pulled, skipped


def main():
    if not os.environ.get("GITHUB_TOKEN") and "--dry-run" not in sys.argv:
        logger.error("GITHUB_TOKEN is not set — cannot sync.")
        sys.exit(1)

    daemon_mode = "--daemon" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if daemon_mode:
        logger.info(
            "Daemon mode: syncing immediately, then every %d seconds. GitHub wins when ahead.",
            DAEMON_INTERVAL_SECONDS,
        )
        while True:
            try:
                sync_once(dry_run=dry_run)
            except Exception as exc:
                logger.error("Sync cycle failed: %s", exc)
            logger.info("Next sync in %d seconds.", DAEMON_INTERVAL_SECONDS)
            time.sleep(DAEMON_INTERVAL_SECONDS)
    else:
        logger.info("Syncing with GitHub (%s/%s)...", GITHUB_OWNER, GITHUB_REPO)
        sync_once(dry_run=dry_run)


if __name__ == "__main__":
    main()
