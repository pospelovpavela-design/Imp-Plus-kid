#!/usr/bin/env python3
"""Чистка онтологии графа концепций.

Имена концепций накопили служебный мусор: хвостовые двоеточия
(«КОМБИНИРИСТИКА:»), склеенные определения («КОМБИНАЦИЯ: ОПРЕДЕЛЕНИЕ: ...»),
внешние кавычки. Из-за этого одна и та же концепция существует под несколькими
именами, а сопоставление имён в когнитивном цикле промахивается.

Скрипт делает ровно две вещи:

1. Выносит определение из имени в поле definition и убирает служебную
   пунктуацию по краям имени.
2. Сливает концепции, чьи имена после нормализации совпадают точно.

Синонимы, которые совпадают лишь по смыслу («КОМБИНАЦИЯ» и «КОМБИНАТОРНОСТЬ»),
скрипт НЕ трогает: их объединение — смысловое решение, а не миграция. Такие
кусты выводятся отдельным списком для ручного разбора.

Запуск:
    python3 scripts/clean_ontology.py                 # только отчёт
    python3 scripts/clean_ontology.py --apply         # записать изменения
    python3 scripts/clean_ontology.py --db path.db    # другая база
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import name_matching  # noqa: E402

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "mind.db"

# Таблицы, ссылающиеся на concepts.id одним столбцом
SINGLE_REF_TABLES = (
    ("concept_groundings", "concept_id"),
    ("concept_working_definitions", "concept_id"),
    ("processing_logs", "concept_id"),
    ("neologisms", "concept_id"),
)
# Таблицы, ссылающиеся на concepts.id парой столбцов
PAIR_REF_TABLES = (
    ("concept_connections", "concept_a_id", "concept_b_id"),
    ("relation_evidence", "concept_a_id", "concept_b_id"),
)
# Таблицы с JSON-списком имён концепций
NAME_LIST_COLUMNS = (
    ("thought_stream", "concepts_involved"),
    ("inquiries", "concept_names"),
    ("beliefs", "concept_names"),
    ("predictions", "concept_names"),
)

_DEFINITION_PREFIX = re.compile(r"^\s*ОПРЕДЕЛЕНИЕ\s*:\s*", re.IGNORECASE)
_SPACES = re.compile(r"\s+")
MAX_NAME_LEN = 60


def clean_name(raw: str) -> tuple[str, str | None]:
    """Имя концепции → (очищенное имя, вынесенное определение или None)."""
    text = _SPACES.sub(" ", str(raw or "")).strip()
    extracted: str | None = None

    head, sep, tail = text.partition(":")
    head_clean = head.strip()
    tail_clean = _DEFINITION_PREFIX.sub("", tail).strip()
    if sep and head_clean and len(head_clean) <= MAX_NAME_LEN and len(tail_clean) >= 15:
        text, extracted = head_clean, tail_clean

    text = text.strip(name_matching._SERVICE_CHARS)
    if not text:
        return str(raw or "").strip(), None
    return text, extracted


def load_plan(conn: sqlite3.Connection) -> dict:
    conn.row_factory = sqlite3.Row
    concepts = [dict(row) for row in conn.execute("SELECT * FROM concepts ORDER BY id")]

    renames: list[tuple[dict, str, str | None]] = []
    for row in concepts:
        cleaned, extracted = clean_name(row["name"])
        row["_clean"] = cleaned
        row["_definition"] = extracted
        if cleaned != row["name"] or extracted:
            renames.append((row, cleaned, extracted))

    groups: dict[str, list[dict]] = collections.OrderedDict()
    for row in concepts:
        groups.setdefault(name_matching.normalize(row["_clean"]), []).append(row)
    merges = [rows for rows in groups.values() if len(rows) > 1]

    # Смысловые дубликаты — только отчёт
    survivors = [rows[0]["_clean"] for rows in groups.values()]
    keys = [name_matching.normalize(name) for name in survivors]
    near: list[tuple[str, str, float]] = []
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            ratio = difflib.SequenceMatcher(None, left, right).ratio()
            if ratio >= 0.82:
                near.append((left, right, ratio))
    near.sort(key=lambda item: item[2], reverse=True)

    long_names = [row["_clean"] for row in concepts if len(row["_clean"]) > MAX_NAME_LEN]
    return {
        "concepts": concepts,
        "renames": renames,
        "merges": merges,
        "near": near,
        "long_names": long_names,
    }


def report(plan: dict) -> None:
    print(f"Концепций всего: {len(plan['concepts'])}")

    print(f"\n[1] Имена под очистку: {len(plan['renames'])}")
    for row, cleaned, extracted in plan["renames"][:25]:
        note = f"  + определение ({len(extracted)} симв.)" if extracted else ""
        print(f"    {row['name'][:58]!r}\n      -> {cleaned[:58]!r}{note}")
    if len(plan["renames"]) > 25:
        print(f"    ... ещё {len(plan['renames']) - 25}")

    merged_away = sum(len(rows) - 1 for rows in plan["merges"])
    print(f"\n[2] Точных дубликатов под слияние: {len(plan['merges'])} групп, "
          f"исчезает концепций: {merged_away}")
    for rows in plan["merges"]:
        keep = rows[0]
        gone = ", ".join(f"id={r['id']} {r['name'][:40]!r}" for r in rows[1:])
        print(f"    оставить id={keep['id']} {keep['_clean'][:45]!r}  <-  {gone}")

    print(f"\n[3] Смысловые дубликаты (НЕ трогаем, разбор вручную): {len(plan['near'])} пар")
    for left, right, ratio in plan["near"][:20]:
        print(f"    {ratio:.2f}  {left[:38]!r} ~ {right[:38]!r}")
    if len(plan["near"]) > 20:
        print(f"    ... ещё {len(plan['near']) - 20}")

    print(f"\n[4] Имена длиннее {MAX_NAME_LEN} символов (НЕ трогаем): {len(plan['long_names'])}")
    for name in plan["long_names"][:10]:
        print(f"    {name[:90]!r}")


def _merge_connection_rows(conn: sqlite3.Connection, affected: set[int]) -> int:
    """Схлопнуть дубли рёбер, возникшие после слияния концепций.

    Затрагиваются только пары с участием слитых концепций: у двух копий одной
    концепции были свои рёбра к общим соседям. Ребро остаётся активным, если
    активной была хотя бы одна из копий.
    """
    if not affected:
        return 0
    removed = 0
    rows = conn.execute(
        """SELECT id, concept_a_id, concept_b_id, strength, confidence,
                  evidence_count, contradiction_count, status
           FROM concept_connections ORDER BY id"""
    ).fetchall()
    best: dict[tuple[int, int], sqlite3.Row] = {}
    for row in rows:
        if row["concept_a_id"] not in affected and row["concept_b_id"] not in affected:
            continue
        key = (min(row["concept_a_id"], row["concept_b_id"]),
               max(row["concept_a_id"], row["concept_b_id"]))
        current = best.get(key)
        if current is None:
            best[key] = row
            continue
        keeper, loser = (current, row)
        if (row["evidence_count"], row["confidence"]) > (
            current["evidence_count"], current["confidence"]
        ):
            keeper, loser = (row, current)
        conn.execute(
            """UPDATE concept_connections
               SET strength=max(strength, ?),
                   confidence=max(confidence, ?),
                   evidence_count=evidence_count + ?,
                   contradiction_count=contradiction_count + ?,
                   status=CASE WHEN ?='active' THEN 'active' ELSE status END
               WHERE id=?""",
            (loser["strength"], loser["confidence"], loser["evidence_count"],
             loser["contradiction_count"], loser["status"], keeper["id"]),
        )
        conn.execute(
            "UPDATE relation_evidence SET connection_id=? WHERE connection_id=?",
            (keeper["id"], loser["id"]),
        )
        conn.execute("DELETE FROM concept_connections WHERE id=?", (loser["id"],))
        best[key] = keeper
        removed += 1
    return removed


def apply_plan(conn: sqlite3.Connection, plan: dict) -> dict:
    stats = collections.Counter()
    name_map: dict[str, str] = {}
    affected: set[int] = set()

    conn.execute("BEGIN")

    # Слияние точных дубликатов
    for rows in plan["merges"]:
        keep = rows[0]
        affected.add(int(keep["id"]))
        for loser in rows[1:]:
            for table, column in SINGLE_REF_TABLES:
                conn.execute(
                    f"UPDATE {table} SET {column}=? WHERE {column}=?",
                    (keep["id"], loser["id"]),
                )
            for table, left, right in PAIR_REF_TABLES:
                conn.execute(f"UPDATE {table} SET {left}=? WHERE {left}=?",
                             (keep["id"], loser["id"]))
                conn.execute(f"UPDATE {table} SET {right}=? WHERE {right}=?",
                             (keep["id"], loser["id"]))
            if not keep["definition"].strip() and loser["definition"].strip():
                conn.execute("UPDATE concepts SET definition=? WHERE id=?",
                             (loser["definition"], keep["id"]))
                keep["definition"] = loser["definition"]
            conn.execute("DELETE FROM concepts WHERE id=?", (loser["id"],))
            name_map[loser["name"]] = keep["_clean"]
            stats["merged"] += 1

    # Петли и дубли рёбер, появившиеся после слияния
    for table, left, right in PAIR_REF_TABLES:
        stats["self_loops"] += conn.execute(
            f"DELETE FROM {table} WHERE {left}={right}"
        ).rowcount
    stats["duplicate_edges"] = _merge_connection_rows(conn, affected)
    stats["duplicate_groundings"] = conn.execute(
        """DELETE FROM concept_groundings WHERE id NOT IN (
               SELECT min(id) FROM concept_groundings GROUP BY concept_id, grounding_id
           )"""
    ).rowcount

    # Очистка имён у выживших концепций
    for row, cleaned, extracted in plan["renames"]:
        if conn.execute("SELECT 1 FROM concepts WHERE id=?", (row["id"],)).fetchone() is None:
            continue
        if cleaned != row["name"]:
            conn.execute("UPDATE concepts SET name=? WHERE id=?", (cleaned, row["id"]))
            name_map[row["name"]] = cleaned
            stats["renamed"] += 1
        if extracted:
            current = conn.execute(
                "SELECT definition FROM concepts WHERE id=?", (row["id"],)
            ).fetchone()[0]
            if len(extracted) > len(str(current or "").strip()):
                conn.execute("UPDATE concepts SET definition=? WHERE id=?",
                             (extracted, row["id"]))
                stats["definitions_moved"] += 1

    # Переписать имена в JSON-списках и в отображаемом фокусе циклов
    if name_map:
        for table, column in NAME_LIST_COLUMNS:
            for row in conn.execute(f"SELECT id, {column} FROM {table}").fetchall():
                try:
                    names = json.loads(row[column] or "[]")
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(names, list):
                    continue
                updated = list(dict.fromkeys(
                    name_map.get(n, n) if isinstance(n, str) else n for n in names
                ))
                if updated != names:
                    conn.execute(
                        f"UPDATE {table} SET {column}=? WHERE id=?",
                        (json.dumps(updated, ensure_ascii=False), row["id"]),
                    )
                    stats[f"names_in_{table}"] += 1

        ordered = sorted(name_map.items(), key=lambda item: len(item[0]), reverse=True)
        for row in conn.execute("SELECT id, focus FROM cognitive_cycles").fetchall():
            focus = row["focus"] or ""
            updated = focus
            for old, new in ordered:
                if old in updated:
                    updated = updated.replace(old, new)
            if updated != focus:
                conn.execute("UPDATE cognitive_cycles SET focus=? WHERE id=?",
                             (updated, row["id"]))
                stats["focus_rewritten"] += 1

    conn.commit()
    return dict(stats)


def _orphan_count(conn: sqlite3.Connection, table: str, column: str) -> int:
    """Ссылки на несуществующие концепции. NULL — не висячая ссылка."""
    return conn.execute(
        f"SELECT count(*) FROM {table} t LEFT JOIN concepts c ON c.id = t.{column} "
        f"WHERE t.{column} IS NOT NULL AND c.id IS NULL"
    ).fetchone()[0]


def verify(conn: sqlite3.Connection) -> None:
    problems = []
    for table, column in SINGLE_REF_TABLES:
        orphans = _orphan_count(conn, table, column)
        if orphans:
            problems.append(f"{table}.{column}: {orphans} висячих ссылок")
    for table, left, right in PAIR_REF_TABLES:
        for column in (left, right):
            orphans = _orphan_count(conn, table, column)
            if orphans:
                problems.append(f"{table}.{column}: {orphans} висячих ссылок")
    dupes = conn.execute(
        "SELECT count(*) FROM (SELECT name FROM concepts GROUP BY name HAVING count(*) > 1)"
    ).fetchone()[0]
    if dupes:
        problems.append(f"concepts.name: {dupes} дубликатов")
    integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
    if integrity != "ok":
        problems.append(f"quick_check: {integrity}")

    print("\nПроверка целостности:", "проблем нет" if not problems else "")
    for line in problems:
        print("   ", line)


def _connect(path: Path, *, write: bool) -> sqlite3.Connection:
    """Соединение с базой. В режиме отчёта запись запрещена на уровне соединения."""
    if write:
        return sqlite3.connect(f"file:{path}?mode=rw", uri=True)
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.execute("SELECT count(*) FROM concepts")
        return conn
    except sqlite3.OperationalError:
        # Копия базы в режиме WAL без сопутствующих -wal/-shm не открывается как ro
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA query_only = ON")
        return conn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--apply", action="store_true", help="записать изменения")
    args = parser.parse_args()

    path = Path(args.db)
    if not path.exists():
        print(f"База не найдена: {path}")
        return 1

    conn = _connect(path, write=args.apply)
    conn.row_factory = sqlite3.Row
    plan = load_plan(conn)
    report(plan)

    if not args.apply:
        print("\nРежим отчёта. Для записи: --apply (сделайте резервную копию базы).")
        return 0

    stats = apply_plan(conn, plan)
    print("\nПрименено:")
    for key, value in sorted(stats.items()):
        print(f"    {key}: {value}")
    verify(conn)
    print(f"\nКонцепций осталось: {conn.execute('SELECT count(*) FROM concepts').fetchone()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
