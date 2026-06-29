#!/usr/bin/env python3
"""
GitHub One-Shot Sync
Pushes changed source files to GitHub via the Contents API.
Called automatically by scripts/post-merge.sh after every agent task.
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

GITHUB_OWNER  = "NDGopher"
GITHUB_REPO   = "UnifiedBetting"
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


def api_request(method: str, path: str, body: dict = None):
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


def get_remote_tree() -> dict:
    result = api_request("GET", f"git/trees/{GITHUB_BRANCH}?recursive=1")
    if not result:
        return {}
    return {
        item["path"]: item["sha"]
        for item in result.get("tree", [])
        if item["type"] == "blob"
    }


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


DAEMON_INTERVAL_SECONDS = 300


def sync_once():
    """Run a single sync cycle. Returns (uploaded, skipped) counts."""
    logger.info("Starting sync cycle...")

    remote_tree = get_remote_tree()
    tracked = get_tracked_files()

    if not tracked:
        logger.warning("No tracked files found.")
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

        local_sha  = git_blob_sha(content)
        remote_sha = remote_tree.get(rel_path)

        if local_sha == remote_sha:
            skipped += 1
            continue

        action = "create" if remote_sha is None else "update"
        logger.info("%s: %s", action, rel_path)

        body = {
            "message": f"auto-sync: {rel_path}",
            "content": base64.b64encode(content).decode(),
            "branch": GITHUB_BRANCH,
        }
        if remote_sha:
            body["sha"] = remote_sha

        if api_request("PUT", f"contents/{rel_path}", body):
            uploaded += 1
            time.sleep(0.3)
        else:
            logger.error("Failed: %s", rel_path)

    if uploaded:
        logger.info("Done: %d file(s) pushed, %d unchanged.", uploaded, skipped)
    else:
        logger.info("Done: all %d files already up to date on GitHub.", skipped)

    return uploaded, skipped


def main():
    if not os.environ.get("GITHUB_TOKEN"):
        logger.error("GITHUB_TOKEN is not set — cannot sync.")
        sys.exit(1)

    daemon_mode = "--daemon" in sys.argv

    if daemon_mode:
        logger.info(
            "Daemon mode: syncing immediately, then every %d seconds.",
            DAEMON_INTERVAL_SECONDS,
        )
        while True:
            try:
                sync_once()
            except Exception as exc:
                logger.error("Sync cycle failed: %s", exc)
            logger.info("Next sync in %d seconds.", DAEMON_INTERVAL_SECONDS)
            time.sleep(DAEMON_INTERVAL_SECONDS)
    else:
        logger.info("Syncing source files to GitHub (%s/%s)...", GITHUB_OWNER, GITHUB_REPO)
        sync_once()


if __name__ == "__main__":
    main()
