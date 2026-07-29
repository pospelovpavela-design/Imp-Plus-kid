"""One evidence-bounded synthesis for each local calendar day."""

from __future__ import annotations

from datetime import date, datetime, time as datetime_time, timedelta
import json
import os
import re
import time
from typing import Any
from zoneinfo import ZoneInfo

import db
import memory_engine
import mind_engine
from time_engine import format_mind_timestamp, get_time_display


DEFAULT_TIMEZONE = "Asia/Chita"
PREFIX = "Сегодня за день я понял, что"


def configured_timezone() -> ZoneInfo:
    name = os.environ.get("MIND_TIMEZONE", DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def local_today(now: float | None = None) -> date:
    timestamp = time.time() if now is None else now
    return datetime.fromtimestamp(timestamp, configured_timezone()).date()


def day_bounds(local_date: date) -> tuple[float, float]:
    timezone = configured_timezone()
    start = datetime.combine(local_date, datetime_time.min, timezone)
    end = start + timedelta(days=1)
    return start.timestamp(), end.timestamp()


def _json_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _json_dict(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _clamp(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _valid_ids(raw: Any, allowed: set[int]) -> list[int]:
    if not isinstance(raw, list):
        return []
    result = []
    for value in raw:
        if isinstance(value, int) and value in allowed and value not in result:
            result.append(value)
    return result


def _clean_continuation(value: Any) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip(" \"'«»")
    text = re.sub(
        r"^Сегодня\s+за\s+день\s+я\s+понял,\s+что\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    if not text:
        text = (
            "надёжный вывод появляется только там, где гипотеза выдерживает "
            "отдельную проверку; остальное остаётся вопросом."
        )
    if text[-1] not in ".!?":
        text += "."
    return text


def _source_context(
    events: list,
    cycles: list,
    beliefs: list,
    predictions: list,
) -> str:
    lines = ["Проверяемые данные локального дня:"]

    accepted_cycles = [
        row
        for row in cycles
        if row["verdict"] in {"accept", "revise"} and float(row["reliability"]) >= 0.65
    ]
    other_cycles = [row for row in cycles if row not in accepted_cycles]
    lines.append(
        f"- Циклов: {len(cycles)}; принято или пересмотрено: {len(accepted_cycles)}; "
        f"не принято: {len(other_cycles)}."
    )

    for row in accepted_cycles:
        candidate = _json_dict(row["candidate_json"])
        critique = _json_dict(row["critique_json"])
        observation = (
            critique.get("revised_observation")
            or candidate.get("observation")
            or critique.get("reason")
            or ""
        )
        lines.append(
            f"- Принятый цикл #{row['id']} ({float(row['reliability']):.2f}, "
            f"{row['focus']}): {str(observation)[:600]}"
        )

    for row in other_cycles[-12:]:
        critique = _json_dict(row["critique_json"])
        lines.append(
            f"- Непринятый цикл #{row['id']} [{row['verdict']}]: "
            f"{str(critique.get('reason') or '')[:350]}"
        )

    for row in events[-50:]:
        content = " ".join(str(row["content"]).split())
        lines.append(
            f"- Событие #{row['id']} [{row['type']}; надёжность "
            f"{float(row['reliability']):.2f}]: {content[:500]}"
        )

    for row in beliefs:
        lines.append(
            f"- Убеждение #{row['id']} ({float(row['confidence']):.2f}): "
            f"{str(row['statement'])[:500]}"
        )

    for row in predictions:
        outcome = row["outcome"] or "ожидает проверки"
        lines.append(
            f"- Прогноз #{row['id']} ({float(row['confidence']):.2f}; {outcome}): "
            f"{str(row['statement'])[:400]}"
        )

    if len(lines) == 2:
        lines.append("- Надёжных событий, убеждений и прогнозов за день нет.")
    return "\n".join(lines)


def _concept_names(events: list, cycles: list, beliefs: list, predictions: list) -> list[str]:
    names: list[str] = []
    for row in events:
        for name in _json_list(row["concepts_involved"]):
            if isinstance(name, str) and name not in names:
                names.append(name)
    for row in beliefs:
        for name in _json_list(row["concept_names"]):
            if isinstance(name, str) and name not in names:
                names.append(name)
    for row in predictions:
        for name in _json_list(row["concept_names"]):
            if isinstance(name, str) and name not in names:
                names.append(name)
    for row in cycles:
        for name in str(row["focus"]).split("↔"):
            cleaned = name.strip()
            if cleaned and cleaned not in names:
                names.append(cleaned)
    return names[:40]


def row_to_dict(row) -> dict:
    return {
        "id": int(row["id"]),
        "local_date": row["local_date"],
        "content": row["content"],
        "confidence": float(row["confidence"]),
        "source_event_ids": _json_list(row["source_event_ids"]),
        "source_cycle_ids": _json_list(row["source_cycle_ids"]),
        "stream_event_id": row["stream_event_id"],
        "created_at": float(row["created_at"]),
        "sent_at": row["sent_at"],
    }


def stream_event_payload(insight: dict) -> dict | None:
    event_id = insight.get("stream_event_id")
    if not isinstance(event_id, int):
        return None
    row = db.get_stream_event(event_id)
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "mind_time": row["mind_time"],
        "type": row["type"],
        "content": row["content"],
        "concepts_involved": _json_list(row["concepts_involved"]),
        "created_at": float(row["created_at"]),
        "salience": float(row["salience"]),
        "reliability": float(row["reliability"]),
        "cycle_id": row["cycle_id"],
    }


async def generate_for_date(
    local_date: date,
    born_at: float,
    *,
    now: float | None = None,
) -> tuple[dict, bool]:
    date_key = local_date.isoformat()
    existing = db.get_daily_insight(date_key)
    if existing:
        return row_to_dict(existing), False

    created_at = time.time() if now is None else now
    start_at, end_at = day_bounds(local_date)
    effective_end = (
        min(end_at, created_at + 0.000001)
        if local_date == local_today(created_at)
        else end_at
    )
    events = db.list_daily_source_events(start_at, effective_end)
    cycles = db.list_daily_source_cycles(start_at, effective_end)
    beliefs = db.list_daily_source_beliefs(start_at, effective_end)
    predictions = db.list_daily_source_predictions(start_at, effective_end)
    concept_names = _concept_names(events, cycles, beliefs, predictions)
    source_context = _source_context(events, cycles, beliefs, predictions)
    td = get_time_display(born_at)
    metrics = db.get_cognitive_metrics()

    candidate = await mind_engine.generate_daily_insight_candidate(
        date_key,
        source_context,
        concept_names,
        td.mind_age_human,
        int(metrics["active_edges"]),
        memory_engine.build_self_context(),
    )
    critique = await mind_engine.critique_daily_insight_candidate(
        date_key,
        candidate,
        source_context,
        concept_names,
        td.mind_age_human,
        int(metrics["active_edges"]),
        memory_engine.build_self_context(),
    )

    allowed_event_ids = {int(row["id"]) for row in events}
    allowed_cycle_ids = {int(row["id"]) for row in cycles}
    critique_event_ids = critique.get("evidence_event_ids")
    candidate_event_ids = candidate.get("evidence_event_ids")
    critique_cycle_ids = critique.get("evidence_cycle_ids")
    candidate_cycle_ids = candidate.get("evidence_cycle_ids")
    source_event_ids = _valid_ids(
        [
            *(critique_event_ids if isinstance(critique_event_ids, list) else []),
            *(candidate_event_ids if isinstance(candidate_event_ids, list) else []),
        ],
        allowed_event_ids,
    )
    source_cycle_ids = _valid_ids(
        [
            *(critique_cycle_ids if isinstance(critique_cycle_ids, list) else []),
            *(candidate_cycle_ids if isinstance(candidate_cycle_ids, list) else []),
        ],
        allowed_cycle_ids,
    )
    continuation = _clean_continuation(
        critique.get("continuation") or candidate.get("continuation")
    )
    content = f"{PREFIX} {continuation}"
    confidence = _clamp(
        critique.get("confidence"),
        _clamp(candidate.get("confidence"), 0.5),
    )
    row, created = db.insert_daily_insight(
        date_key,
        content,
        confidence,
        source_event_ids,
        source_cycle_ids,
        {"candidate": candidate, "critique": critique},
        format_mind_timestamp(born_at, created_at),
        concept_names,
        created_at,
    )
    return row_to_dict(row), created


async def maybe_generate_today(
    born_at: float,
    *,
    now: float | None = None,
) -> tuple[dict, bool] | None:
    timestamp = time.time() if now is None else now
    local_now = datetime.fromtimestamp(timestamp, configured_timezone())
    try:
        minimum_hour = max(0, min(23, int(os.environ.get("DAILY_INSIGHT_HOUR", 21))))
    except ValueError:
        minimum_hour = 21
    if local_now.hour < minimum_hour:
        return None
    return await generate_for_date(local_now.date(), born_at, now=timestamp)
