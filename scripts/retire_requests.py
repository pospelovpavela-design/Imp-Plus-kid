#!/usr/bin/env python3
"""Снять с очереди просьбы к оператору, составленные по негодной схеме.

До 25 августа 2026 прогнозы и просьбы разум проверял собственной будущей
памятью: «извлечь выборку эпизодов», «мониторить консолидации». Такая проверка
подтверждается всегда, ответить на неё внешним свидетельством нельзя. Накопилось
48 таких просьб, все про один фокус.

Снятая просьба получает статус `retired` и выпадает из вкладки «Разум
спрашивает», но остаётся в базе: это часть истории, а не мусор.

Запуск:
    python3 scripts/retire_requests.py                  # только отчёт
    python3 scripts/retire_requests.py --apply
    python3 scripts/retire_requests.py --before 1787700000 --apply
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import db  # noqa: E402

REASON = (
    "Снята: проверка опиралась на собственную будущую память, "
    "внешним свидетельством такая просьба не закрывается."
)


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
    parser.add_argument(
        "--before",
        type=float,
        default=time.time(),
        help="снимать просьбы, созданные раньше этой отметки (по умолчанию — все текущие)",
    )
    args = parser.parse_args()

    conn = connect(Path(args.db), write=args.apply)
    rows = conn.execute(
        """SELECT id, question, created_at FROM inquiries
           WHERE origin = ? AND status IN ('open', 'blocked') AND created_at < ?
           ORDER BY id""",
        (db.OPERATOR_REQUEST_ORIGIN, args.before),
    ).fetchall()

    print(f"Просьб под снятие: {len(rows)}")
    for row in rows[:5]:
        print(f"    #{row['id']} {row['question'][:90]}")
    if len(rows) > 5:
        print(f"    ... ещё {len(rows) - 5}")

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
        """SELECT COUNT(*) FROM inquiries
           WHERE origin = ? AND status IN ('open', 'blocked')""",
        (db.OPERATOR_REQUEST_ORIGIN,),
    ).fetchone()[0]
    print(f"\nСнято: {len(rows)}. Осталось открытых просьб: {left}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
