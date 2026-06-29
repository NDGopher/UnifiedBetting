#!/usr/bin/env python3
"""
GitHub Auto-Sync Daemon
Pushes source-code changes to GitHub via the Contents API every SYNC_INTERVAL seconds.
Uses git ls-files to determine which files to sync (respects .gitignore).
Requires the GITHUB_TOKEN secret.
"""

import os
import base64
import hashlib
import subprocess
import time
import logging
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

GITHUB_OWNER = "NDGopher"
GITHUB_REPO  = "UnifiedBetting"
GITHUB_BRANCH = "main"
SYNC_INTERVAL = int(os.environ.get("GITHUB_SYNC_INTERVAL", "300"))
REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories/prefixes to always skip even if somehow tracked by git
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [github-autosync] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("github-autosync")


def git_blob_sha(content: bytes) -> str:
    """Compute the git blob SHA1 for file content (same algo GitHub uses)."""
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def api_request(method: str, path: str, body: dict = None) -> dict | None:
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
        logger.error("GitHub API %s %s → %s: %s", method, path, e.code, body_text[:200])
        return None
    except Exception as exc:
        logger.error("GitHub API error %s %s: %s", method, path, exc)
        return None


def get_remote_tree() -> dict[str, str]:
    """Return {path: blob_sha} for all files on GitHub main branch."""
    result = api_request("GET", f"git/trees/{GITHUB_BRANCH}?recursive=1")
    if not result or result.get("truncated"):
        if result and result.get("truncated"):
            logger.warning("GitHub tree was truncated — very large repo. Will still attempt sync.")
        elif not result:
            return {}
    return {
        item["path"]: item["sha"]
        for item in result.get("tree", [])
        if item["type"] == "blob"
    }


def get_tracked_files() -> list[str]:
    """Return repo-relative paths of all git-tracked source files."""
    try:
        out = subprocess.check_output(
            ["git", "ls-files"],
            cwd=str(REPO_ROOT),
            text=True,
            timeout=15,
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


def get_file_sha_on_github(path: str) -> str | None:
    """Get the current blob SHA for a file on GitHub (used for updates)."""
    result = api_request("GET", f"contents/{path}?ref={GITHUB_BRANCH}")
    if result and "sha" in result:
        return result["sha"]
    return None


def upload_file(rel_path: str, local_sha: str, remote_sha: str | None) -> bool:
    abs_path = REPO_ROOT / rel_path
    try:
        content = abs_path.read_bytes()
    except Exception as exc:
        logger.warning("Cannot read %s: %s", rel_path, exc)
        return False

    body: dict = {
        "message": f"auto-sync: update {rel_path}",
        "content": base64.b64encode(content).decode(),
        "branch": GITHUB_BRANCH,
    }
    if remote_sha:
        body["sha"] = remote_sha

    result = api_request("PUT", f"contents/{rel_path}", body)
    return result is not None


def run_sync() -> tuple[int, int]:
    """Sync changed source files. Returns (uploaded, skipped)."""
    logger.info("Starting sync cycle...")

    remote_tree = get_remote_tree()
    if not remote_tree and remote_tree is not None:
        logger.info("Remote tree is empty — will upload all tracked files.")

    tracked = get_tracked_files()
    if not tracked:
        logger.warning("No tracked files found via git ls-files.")
        return 0, 0

    uploaded = 0
    skipped  = 0

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

        action = "create" if remote_sha is None else "update"
        logger.info("%s: %s", action, rel_path)

        if upload_file(rel_path, local_sha, remote_sha):
            uploaded += 1
            time.sleep(0.3)
        else:
            logger.error("Failed to upload %s", rel_path)

    return uploaded, skipped


def main():
    logger.info(
        "GitHub Auto-Sync daemon starting (API mode). Interval: %ds. Repo: %s/%s",
        SYNC_INTERVAL, GITHUB_OWNER, GITHUB_REPO,
    )

    if not os.environ.get("GITHUB_TOKEN"):
        logger.error("GITHUB_TOKEN is not set — cannot sync. Set it in Replit Secrets.")

    while True:
        if os.environ.get("GITHUB_TOKEN"):
            uploaded, skipped = run_sync()
            if uploaded:
                logger.info("Sync complete: %d file(s) updated, %d unchanged.", uploaded, skipped)
            else:
                logger.info("Sync complete: all %d tracked files already up to date.", skipped)
        else:
            logger.error("Skipping sync — GITHUB_TOKEN not set.")

        time.sleep(SYNC_INTERVAL)


if __name__ == "__main__":
    main()
