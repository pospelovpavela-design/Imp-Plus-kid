#!/usr/bin/env python3
"""Снять с очереди вопросы, заведённые слепым разумом.

До 23 августа 2026 когнитивный цикл получал только имена концепций — без
определений — и поэтому раз за разом упирался в «различительный признак не
обнаружен». Каждый такой цикл заводил новые вопросы, и очередь выросла до
полутора тысяч, три четверти которых про одну пару концепций. Она ведёт три
цикла из четырёх, и разум переотвечает на вопросы, которые задал, будучи слепым.

Снимается вопрос, который одновременно: старше указанного возраста, ни разу не
пробован и не является просьбой к оператору. Свежие и уже начатые остаются.

Запуск:
    python3 scripts/retire_inquiries.py                 # только отчёт
    python3 scripts/retire_inquiries.py --apply
    python3 scripts/retire_inquiries.py --days 3 --apply
"""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import db  # noqa: E402

REASON = "Снят: задан до того, как цикл начал видеть определения концепций."


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
    parser.add_argument("--days", type=float, default=7.0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    cutoff = time.time() - args.days * 86400
    conn = connect(Path(args.db), write=args.apply)
    rows = conn.execute(
        """SELECT id, question, concept_names, origin FROM inquiries
           WHERE status IN ('open', 'blocked')
             AND attempts = 0
             AND created_at < ?
             AND origin <> ?""",
        (cutoff, db.OPERATOR_REQUEST_ORIGIN),
    ).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM inquiries WHERE status IN ('open', 'blocked')"
    ).fetchone()[0]
    print(f"Открытых вопросов: {total}")
    print(f"Под снятие (старше {args.days:g} сут., ни разу не пробованы): {len(rows)}")

    by_origin = collections.Counter(row["origin"] for row in rows)
    for origin, count in by_origin.most_common():
        print(f"    {origin}: {count}")
    by_concepts = collections.Counter(
        tuple(sorted(json.loads(row["concept_names"] or "[]"))) for row in rows
    )
    print("  по набору концепций:")
    for names, count in by_concepts.most_common(3):
        print(f"    {count:5d}  {', '.join(names)[:60]}")

    if not args.apply:
        print("\nРежим отчёта. Для записи: --apply")
        return 0

    now = time.time()
    conn.executemany(
        """UPDATE inquiries
           SET status='retired', last_result=?, next_attempt_at=?, updated_at=?
           WHERE id=?""",
        [(REASON, now, now, int(row["id"])) for row in rows],
    )
    conn.commit()
    left = conn.execute(
        "SELECT COUNT(*) FROM inquiries WHERE status IN ('open', 'blocked')"
    ).fetchone()[0]
    print(f"\nСнято: {len(rows)}. Осталось открытых: {left}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
