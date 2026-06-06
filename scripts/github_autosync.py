#!/usr/bin/env python3
"""
GitHub Auto-Sync Daemon
Runs in the background and pushes new commits to GitHub every SYNC_INTERVAL_SECONDS.
Requires the GITHUB_TOKEN secret to be set.
"""

import os
import subprocess
import time
import logging
import sys
from pathlib import Path

SYNC_INTERVAL_SECONDS = int(os.environ.get("GITHUB_SYNC_INTERVAL", "300"))
REPO_ROOT = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = REPO_ROOT / "scripts" / "github_sync.sh"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [github-autosync] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("github-autosync")


def check_prerequisites() -> bool:
    if not os.environ.get("GITHUB_TOKEN"):
        logger.error(
            "GITHUB_TOKEN secret is not configured. "
            "Set it in Replit Secrets to enable auto-sync."
        )
        return False
    if not SYNC_SCRIPT.exists():
        logger.error("Sync script not found at %s", SYNC_SCRIPT)
        return False
    return True


def run_sync() -> bool:
    try:
        result = subprocess.run(
            ["bash", str(SYNC_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                logger.info(line)
        if result.returncode != 0:
            if result.stderr.strip():
                logger.error("Sync failed: %s", result.stderr.strip())
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("Sync script timed out after 60 seconds.")
        return False
    except Exception as exc:
        logger.error("Unexpected error during sync: %s", exc)
        return False


def main():
    logger.info(
        "GitHub Auto-Sync daemon starting. Sync interval: %ds. Repo: %s",
        SYNC_INTERVAL_SECONDS,
        REPO_ROOT,
    )

    if not check_prerequisites():
        logger.error("Prerequisites not met. Daemon will keep retrying every %ds.", SYNC_INTERVAL_SECONDS)

    while True:
        if check_prerequisites():
            run_sync()
        time.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
