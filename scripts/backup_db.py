#!/usr/bin/env python3
"""Create and verify a consistent online backup of the IMPLUS SQLite database."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import time


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=project_root / "data" / "mind.db",
        help="SQLite database to back up",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=project_root / "backups",
        help="Directory that receives backup files",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=124,
        help="Maximum number of completed backups to retain",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prune_backups(destination: Path, keep: int) -> int:
    backups = sorted(
        destination.glob("mind-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    removed = 0
    for path in backups[keep:]:
        path.unlink()
        removed += 1
    return removed


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    destination = args.destination.resolve()

    if args.keep < 1:
        print("--keep must be at least 1", file=sys.stderr)
        return 2
    if not source.is_file():
        print(f"Database not found: {source}", file=sys.stderr)
        return 2

    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination, 0o700)

    lock_path = destination / ".backup.lock"
    lock_handle = lock_path.open("w")
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another backup is already running; skipping")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    target = destination / f"mind-{stamp}.db"
    temporary = destination / f".{target.name}.tmp"

    try:
        source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        backup_db = sqlite3.connect(temporary)
        try:
            source_db.backup(backup_db, pages=1000, sleep=0.05)
            journal_mode = backup_db.execute("PRAGMA journal_mode=DELETE").fetchone()
            if not journal_mode or journal_mode[0].lower() != "delete":
                raise RuntimeError(f"Could not finalize backup journal: {journal_mode!r}")
            result = backup_db.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise RuntimeError(f"SQLite quick_check failed: {result!r}")
        finally:
            backup_db.close()
            source_db.close()

        os.chmod(temporary, 0o600)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        removed = prune_backups(destination, args.keep)
        print(
            f"backup={target} bytes={target.stat().st_size} "
            f"sha256={sha256(target)} quick_check=ok pruned={removed}"
        )
        return 0
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
