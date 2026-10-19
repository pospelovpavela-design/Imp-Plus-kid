#!/usr/bin/env python3
"""Перебалансировать приоритеты накопленной очереди вопросов.

Потолок приоритета действует только на вновь создаваемые вопросы, а в очереди
уже лежат сотни заведённых по старым правилам: консолидация назначала себе до
1.0 и навсегда выигрывала сортировку, из-за чего за 400 циклов ни одно
противоречие не было взято в работу.

Скрипт приводит накопленное к новым правилам: противоречия поднимаются,
консолидация опускается. Содержание вопросов не меняется.

Запуск:
    python3 scripts/rebalance_queue.py            # только отчёт
    python3 scripts/rebalance_queue.py --apply
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import cognitive_engine  # noqa: E402
import db  # noqa: E402

OPEN = ("open", "blocked")


def connect(path: Path, *, write: bool) -> sqlite3.Connection:
    if write:
        conn = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
    else:
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(db.DB_PATH))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = connect(Path(args.db), write=args.apply)
    plan = [
        ("critic_contradiction", cognitive_engine.CONTRADICTION_PRIORITY, "priority < ?"),
        ("consolidation", cognitive_engine.CONSOLIDATION_PRIORITY_CAP, "priority > ?"),
    ]
    for origin, target, condition in plan:
        count = conn.execute(
            f"""SELECT COUNT(*) FROM inquiries
                WHERE origin = ? AND status IN {OPEN} AND {condition}""",
            (origin, target),
        ).fetchone()[0]
        print(f"  {origin:22s} -> приоритет {target}: затронет {count}")

    if not args.apply:
        print("\nРежим отчёта. Для записи: --apply")
        return 0

    now = time.time()
    for origin, target, condition in plan:
        conn.execute(
            f"""UPDATE inquiries SET priority = ?, updated_at = ?
                WHERE origin = ? AND status IN {OPEN} AND {condition}""",
            (target, now, origin, target),
        )
    conn.commit()

    row = conn.execute(
        f"""SELECT origin, priority FROM inquiries
            WHERE status IN {OPEN} AND next_attempt_at <= ?
            ORDER BY priority DESC, updated_at ASC LIMIT 1""",
        (now,),
    ).fetchone()
    print(f"\nСледующим в работу пойдёт: {row['origin']} (приоритет {row['priority']})" if row else "\nОчередь пуста")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
