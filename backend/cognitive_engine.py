"""Evidence-gated cognition built on memory, inquiry, criticism, and feedback."""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter
from typing import Any

import db
import memory_engine
import mind_engine
import name_matching
from time_engine import format_mind_timestamp, get_time_display

logger = logging.getLogger("cognitive_engine")


def _json_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _clamp(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _grounding_context(names: list[str], limit: int = 6) -> str:
    rows = db.find_groundings_for_concept_names(names, limit=limit)
    if not rows:
        return "Для выбранного фокуса нет текстовых оснований."
    lines = []
    for row in rows:
        excerpt = " ".join(str(row["excerpt"]).split())
        note = f" Привязка: {row['note']}." if row["note"] else ""
        lines.append(
            f"- Основание для «{row['concept_name']}».{note} {excerpt[:800]}"
        )
    return "\n".join(lines)


def initialize(now: float | None = None) -> None:
    memory_engine.initialize_self_model(now)


def _seed_inquiry(now: float) -> None:
    candidates = db.list_concepts_needing_grounding(limit=100)
    if not candidates:
        return
    cursor_raw = db.get_cognitive_state("grounding_seed_cursor")
    try:
        cursor = int(cursor_raw or 0) % len(candidates)
    except ValueError:
        cursor = 0
    selected = [candidates[cursor]]
    if len(candidates) > 1:
        selected.append(candidates[(cursor + 1) % len(candidates)])
    db.set_cognitive_state(
        "grounding_seed_cursor",
        str((cursor + len(selected)) % len(candidates)),
        now,
    )
    names = [row["name"] for row in selected]
    if len(names) == 1:
        question = (
            f"Какое внешнее наблюдение позволит отличить концепцию «{names[0]}» "
            "от незаземлённого ярлыка?"
        )
    else:
        question = (
            f"Какое наблюдаемое различие отделяет «{names[0]}» от «{names[1]}», "
            "и какое свидетельство могло бы это опровергнуть?"
        )
    db.create_inquiry(question, names, 0.65, "grounding_gap", now)


def _resolve_names(raw: Any, index: dict[str, str]) -> list[str]:
    names = [
        name_matching.resolve(name, index)
        for name in (raw or [])
        if isinstance(name, str)
    ]
    return [name for name in names if name is not None]


def _select_focus(graph: Any, inquiry: Any | None, now: float) -> tuple[list[str], Any | None]:
    if inquiry is None:
        _seed_inquiry(now)
        inquiry = db.get_next_inquiry(now)

    known = name_matching.build_index(graph.all_names())
    if inquiry is not None:
        names = [
            resolved
            for resolved in (
                name_matching.resolve(name, known)
                for name in _json_list(inquiry["concept_names"])
                if isinstance(name, str)
            )
            if resolved is not None
        ]
        if names:
            return list(dict.fromkeys(names)), inquiry

    pair = graph.random_two_concepts()
    if pair is None:
        return [], inquiry
    return [pair[0]["name"], pair[1]["name"]], inquiry


async def run_cycle(
    graph: Any,
    born_at: float,
    *,
    trigger: str = "scheduled",
) -> dict | None:
    now = time.time()
    inquiry = db.get_next_inquiry(now)
    focus_names, inquiry = _select_focus(graph, inquiry, now)
    if not focus_names:
        return None

    inquiry_text = str(inquiry["question"]) if inquiry is not None else None
    focus = " ↔ ".join(focus_names)
    query = f"{focus}. {inquiry_text or ''}".strip()
    memories = memory_engine.retrieve_memories(query, focus_names, limit=8, now=now)
    self_context = memory_engine.build_self_context()
    groundings = _grounding_context(focus_names)
    available_names = graph.relevant_names(focus_names, limit=36)
    if not available_names:
        available_names = focus_names
    td = get_time_display(born_at)

    candidate = await mind_engine.generate_cognitive_candidate(
        focus,
        inquiry_text,
        available_names,
        td.mind_age_human,
        graph.edge_count(),
        memories.text,
        groundings,
        self_context,
    )
    critique = await mind_engine.critique_cognitive_candidate(
        candidate,
        focus,
        inquiry_text,
        available_names,
        td.mind_age_human,
        graph.edge_count(),
        memories.text,
        groundings,
        self_context,
    )

    verdict = str(critique.get("verdict") or "reject").strip().casefold()
    if verdict not in {"accept", "revise", "needs_evidence", "reject"}:
        verdict = "reject"
    reliability = _clamp(critique.get("reliability"), 0.0)
    cycle_id = db.insert_cognitive_cycle(
        trigger,
        focus,
        candidate,
        critique,
        memories.event_ids,
        verdict,
        reliability,
        now,
        inquiry_id=int(inquiry["id"]) if inquiry is not None else None,
    )

    observation = str(
        critique.get("revised_observation")
        or candidate.get("observation")
        or "Гипотеза не сформулирована."
    ).strip()
    reason = str(critique.get("reason") or "").strip()
    if verdict in {"needs_evidence", "reject"}:
        content = f"Гипотеза не принята ({verdict}): {observation}"
        if reason:
            content += f" Проверка: {reason}"
    else:
        content = observation
        if candidate.get("uncertainty"):
            content += f" Неопределённость: {str(candidate['uncertainty']).strip()}"

    event_id = db.insert_stream_event(
        format_mind_timestamp(born_at, now),
        "cognitive",
        content,
        focus_names,
        now,
        salience=0.8 if verdict in {"accept", "revise"} else 0.45,
        reliability=reliability,
        cycle_id=cycle_id,
    )

    name_index = name_matching.build_index(available_names)
    unresolved: list[str] = []

    def lookup(raw: Any) -> Any:
        """Имя из ответа модели → строка концепции. Потери не молчат."""
        resolved = name_matching.resolve(str(raw or ""), name_index)
        if resolved is None:
            text = " ".join(str(raw or "").split())
            if text:
                unresolved.append(text)
            return None
        return db.get_concept_by_name(resolved)
    accepted_pairs: set[tuple[int, int, str]] = set()
    if verdict in {"accept", "revise"} and reliability >= 0.65:
        for relation in critique.get("accepted_relations") or []:
            if not isinstance(relation, dict):
                continue
            source = lookup(relation.get("source"))
            target = lookup(relation.get("target"))
            label = " ".join(str(relation.get("relationship", "")).split())
            confidence = _clamp(relation.get("confidence"), 0.0)
            strength = _clamp(relation.get("strength"), 0.5)
            if not source or not target or source["id"] == target["id"]:
                continue
            if not label or confidence < 0.6:
                continue
            changed = graph.add_connection(
                source["id"],
                target["id"],
                label,
                strength,
                source="critic_accepted",
                confidence=confidence,
            )
            connection = db.get_connection_between(source["id"], target["id"])
            connection_id = int(connection["id"]) if connection else None
            db.record_relation_evidence(
                source["id"],
                target["id"],
                label,
                "accept" if changed else "support",
                confidence,
                now,
                connection_id=connection_id,
                source_event_id=event_id,
                cycle_id=cycle_id,
                reason=str(relation.get("reason") or reason)[:1000],
            )
            accepted_pairs.add(
                (min(source["id"], target["id"]), max(source["id"], target["id"]), label)
            )

    if verdict in {"needs_evidence", "reject"}:
        for relation in candidate.get("relations") or []:
            if not isinstance(relation, dict):
                continue
            source = lookup(relation.get("source"))
            target = lookup(relation.get("target"))
            label = " ".join(str(relation.get("relationship", "")).split())
            if not source or not target or source["id"] == target["id"] or not label:
                continue
            existing = db.get_connection_between(source["id"], target["id"])
            db.record_relation_evidence(
                source["id"],
                target["id"],
                label,
                "reject",
                _clamp(relation.get("confidence"), 0.0),
                now,
                connection_id=int(existing["id"]) if existing else None,
                source_event_id=event_id,
                cycle_id=cycle_id,
                reason=reason[:1000],
            )
            graph.sync_connection(source["id"], target["id"])

    if unresolved:
        top = ", ".join(f"{name} ×{n}" for name, n in Counter(unresolved).most_common(5))
        logger.warning(
            "Cycle %d: %d relation endpoint(s) did not match a graph concept: %s",
            cycle_id,
            len(unresolved),
            top,
        )

    next_question = candidate.get("next_question")
    if isinstance(next_question, str) and next_question.strip():
        db.create_inquiry(
            next_question,
            focus_names,
            0.65 if verdict == "needs_evidence" else 0.5,
            "cognitive_cycle",
            now,
        )
    for contradiction in critique.get("contradictions") or []:
        if isinstance(contradiction, str) and contradiction.strip():
            db.create_inquiry(
                f"Как проверить противоречие: {contradiction.strip()}",
                focus_names,
                0.8,
                "critic_contradiction",
                now,
            )

    prediction = candidate.get("prediction")
    prediction_id = None
    if (
        verdict in {"accept", "revise"}
        and isinstance(prediction, dict)
        and str(prediction.get("statement") or "").strip()
        and str(prediction.get("test_method") or "").strip()
    ):
        confidence = _clamp(prediction.get("confidence"), 0.0)
        if confidence >= 0.5:
            prediction_id = db.insert_prediction(
                str(prediction["statement"]),
                str(prediction["test_method"]),
                focus_names,
                confidence,
                now,
                cycle_id=cycle_id,
            )

    if inquiry is not None:
        db.record_inquiry_attempt(
            int(inquiry["id"]),
            content,
            bool(critique.get("inquiry_resolved"))
            and verdict in {"accept", "revise"},
            now,
        )

    return {
        "id": event_id,
        "mind_time": format_mind_timestamp(born_at, now),
        "type": "cognitive",
        "content": content,
        "concepts_involved": focus_names,
        "created_at": now,
        "cycle_id": cycle_id,
        "verdict": verdict,
        "reliability": reliability,
        "prediction_id": prediction_id,
        "accepted_relations": len(accepted_pairs),
        "unresolved_names": len(unresolved),
    }


async def maybe_consolidate(graph: Any, born_at: float) -> dict | None:
    now = time.time()
    interval = int(os.environ.get("CONSOLIDATION_INTERVAL_SECONDS", 21600))
    last_raw = db.get_cognitive_state("last_consolidation_at")
    last = float(last_raw) if last_raw else 0.0
    if now - last < interval:
        return None

    events = db.list_unconsolidated_events(limit=12)
    minimum = int(os.environ.get("CONSOLIDATION_MIN_EVENTS", 6))
    if len(events) < minimum:
        return None

    event_dicts = [dict(row) for row in events]
    event_ids = [int(row["id"]) for row in events]
    concept_names = []
    for row in events:
        for name in _json_list(row["concepts_involved"]):
            if isinstance(name, str) and name not in concept_names:
                concept_names.append(name)
    available_names = graph.relevant_names(concept_names, limit=40) or concept_names
    beliefs = [dict(row) for row in db.list_beliefs(limit=20)]
    td = get_time_display(born_at)
    result = await mind_engine.consolidate_memory_batch(
        event_dicts,
        beliefs,
        available_names,
        td.mind_age_human,
        graph.edge_count(),
        memory_engine.build_self_context(),
    )
    summary = " ".join(str(result.get("summary") or "").split()).strip()
    if not summary:
        db.insert_consolidation_run(event_ids, "", result, "rejected", now)
        db.set_cognitive_state("last_consolidation_at", str(now), now)
        return None

    allowed_ids = set(event_ids)
    known = name_matching.build_index(graph.all_names())
    for item in result.get("beliefs") or []:
        if not isinstance(item, dict):
            continue
        evidence = [
            int(value)
            for value in item.get("evidence_event_ids") or []
            if isinstance(value, int) and value in allowed_ids
        ]
        confidence = _clamp(item.get("confidence"), 0.0)
        statement = str(item.get("statement") or "").strip()
        names = _resolve_names(item.get("concept_names"), known)
        if statement and evidence and confidence >= 0.65:
            db.upsert_belief(statement, names, confidence, evidence, now)

    for item in result.get("inquiries") or []:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        names = _resolve_names(item.get("concept_names"), known)
        if question:
            db.create_inquiry(
                question,
                names,
                _clamp(item.get("priority"), 0.5),
                "consolidation",
                now,
            )

    db.mark_events_consolidated(event_ids)
    db.insert_consolidation_run(event_ids, summary, result, "accepted", now)
    db.set_cognitive_state("last_consolidation_at", str(now), now)
    event_id = db.insert_stream_event(
        format_mind_timestamp(born_at, now),
        "consolidation",
        summary,
        concept_names,
        now,
        salience=0.85,
        reliability=0.75,
        consolidated=True,
    )
    return {
        "id": event_id,
        "mind_time": format_mind_timestamp(born_at, now),
        "type": "consolidation",
        "content": summary,
        "concepts_involved": concept_names,
        "created_at": now,
    }
