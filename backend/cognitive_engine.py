"""Evidence-gated cognition built on memory, inquiry, criticism, and feedback."""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from collections import Counter
from typing import Any

import db
import memory_engine
import mind_engine
import name_matching
from time_engine import format_mind_timestamp, get_time_display

logger = logging.getLogger("cognitive_engine")

DEFAULT_PREDICTION_HORIZON_DAYS = 7.0
MIN_PREDICTION_HORIZON_DAYS = 1.0
MAX_PREDICTION_HORIZON_DAYS = 30.0
# Истёкший прогноз — не опровержение, поэтому убеждение слабеет мягко
EXPIRED_BELIEF_FACTOR = 0.85
# Опровержение внешним наблюдением бьёт по убеждению заметно сильнее
DISCONFIRMED_BELIEF_FACTOR = 0.55
# Каждый N-й цикл выбирает фокус в обход очереди вопросов
EXPLORATION_EVERY_DEFAULT = 4
# Больше вопросов про один и тот же набор концепций не заводим
MAX_OPEN_INQUIRIES_PER_FOCUS = 12
# Одно наблюдение не может закрыть весь запас прогнозов
OBSERVATION_CANDIDATE_LIMIT = 5
OBSERVATION_MAX_RESOLUTIONS = 3
# Доля слов свидетельства, которая обязана встретиться в самом наблюдении
EVIDENCE_QUOTE_RATIO = 0.6
# Меньше этого числа имён рабочий набор цикла вырождается
MIN_WORKING_NAMES = 12
# Отбор связей: как часто, сколько связей за раз, сколько соседей у концепции
GRAPH_SELECTION_INTERVAL_DEFAULT = 86400
GRAPH_SELECTION_BUDGET_DEFAULT = 60
GRAPH_DEGREE_CAP_DEFAULT = 24

_WORD_RE = re.compile(r"[^\W_]{3,}", flags=re.UNICODE)


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


def _positive_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _exploration_due(now: float) -> bool:
    """Каждый N-й цикл идёт в обход очереди вопросов.

    Очередь кормит сама себя: каждый цикл заводит новые вопросы с теми же
    именами, поэтому без принудительной квоты исследование не запускается
    никогда — случайная пара выбиралась только при пустой очереди.
    """
    every = _positive_env("COGNITIVE_EXPLORATION_EVERY", EXPLORATION_EVERY_DEFAULT)
    raw = db.get_cognitive_state("cycle_counter")
    try:
        counter = int(raw or 0) + 1
    except ValueError:
        counter = 1
    db.set_cognitive_state("cycle_counter", str(counter), now)
    return counter % every == 0


def _explore_focus(graph: Any, now: float) -> list[str]:
    """Пара концепций для исследования: приоритет наименее заземлённым."""
    known = name_matching.build_index(graph.all_names())
    pool: list[str] = []
    for row in db.list_concepts_needing_grounding(limit=60):
        resolved = name_matching.resolve(row["name"], known)
        if resolved is not None and resolved not in pool:
            pool.append(resolved)
    if len(pool) >= 2:
        raw = db.get_cognitive_state("exploration_cursor")
        try:
            cursor = int(raw or 0)
        except ValueError:
            cursor = 0
        first = pool[cursor % len(pool)]
        db.set_cognitive_state("exploration_cursor", str((cursor + 1) % len(pool)), now)
        second = random.choice([name for name in pool if name != first])
        return [first, second]
    pair = graph.random_two_concepts()
    return [pair[0]["name"], pair[1]["name"]] if pair else []


def _working_names(
    graph: Any,
    focus_names: list[str],
    remembered: list[str],
    limit: int = 36,
) -> list[str]:
    """Имена, с которыми цикл работает.

    Соседей может не быть вовсе: концепция бывает изолированной, и тогда набор
    вырождается в одно имя, а требование «связывай только имена из списка»
    становится невыполнимым. Добираем тем, что упоминалось рядом в памяти, затем
    наименее заземлёнными концепциями — там структуры меньше всего.
    """
    names = list(
        dict.fromkeys(graph.relevant_names(focus_names, limit=limit) or focus_names)
    )
    if len(names) >= MIN_WORKING_NAMES:
        return names

    index = name_matching.build_index(graph.all_names())
    for raw in remembered:
        resolved = name_matching.resolve(raw, index)
        if resolved is not None and resolved not in names:
            names.append(resolved)
        if len(names) >= limit:
            return names

    for row in db.list_concepts_needing_grounding(limit=limit):
        if len(names) >= MIN_WORKING_NAMES:
            break
        if row["name"] not in names:
            names.append(row["name"])
    return names


def _prediction_horizon_seconds(raw: Any) -> float:
    """Срок проверки в секундах. Без срока прогноз нельзя ни закрыть, ни опровергнуть."""
    try:
        days = float(raw)
    except (TypeError, ValueError):
        days = DEFAULT_PREDICTION_HORIZON_DAYS
    days = max(MIN_PREDICTION_HORIZON_DAYS, min(MAX_PREDICTION_HORIZON_DAYS, days))
    return days * 86400.0


def initialize(now: float | None = None) -> None:
    memory_engine.initialize_self_model(now)
    filled = db.backfill_prediction_deadlines(
        now or time.time(),
        _prediction_horizon_seconds(DEFAULT_PREDICTION_HORIZON_DAYS),
    )
    if filled:
        logger.info("Assigned a verification deadline to %d older prediction(s)", filled)


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
    if _exploration_due(now):
        explored = _explore_focus(graph, now)
        if len(explored) >= 2:
            logger.info("Exploration cycle: focus %s", " ↔ ".join(explored))
            return explored, None

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
    available_names = _working_names(graph, focus_names, memories.concept_names)
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

    # Сопоставляем по всему графу, а не по рабочему набору: концепция, названная
    # по памяти, существует, и терять связь из-за того, что её не показали, — та
    # же немая потеря, ради которой всё это чинилось.
    name_index = name_matching.build_index(graph.all_names())
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

    open_for_focus = db.count_open_inquiries_for_concepts(focus_names)
    if open_for_focus >= MAX_OPEN_INQUIRIES_PER_FOCUS:
        logger.info(
            "Focus %s already has %d open inquiries; not adding more",
            focus,
            open_for_focus,
        )
    else:
        next_question = candidate.get("next_question")
        if isinstance(next_question, str) and next_question.strip():
            db.create_inquiry(
                next_question,
                focus_names,
                0.65 if verdict == "needs_evidence" else 0.5,
                "cognitive_cycle",
                now,
            )
            open_for_focus += 1
        for contradiction in critique.get("contradictions") or []:
            if open_for_focus >= MAX_OPEN_INQUIRIES_PER_FOCUS:
                break
            if isinstance(contradiction, str) and contradiction.strip():
                db.create_inquiry(
                    f"Как проверить противоречие: {contradiction.strip()}",
                    focus_names,
                    0.8,
                    "critic_contradiction",
                    now,
                )
                open_for_focus += 1

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
                expected_by=now + _prediction_horizon_seconds(
                    prediction.get("horizon_days")
                ),
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


def _weaken_beliefs_behind(prediction: Any, factor: float, event_id: int, now: float) -> int:
    """Ослабить убеждения, опирающиеся на цикл, который породил прогноз."""
    cycle_id = prediction["cycle_id"]
    if cycle_id is None:
        return 0
    source_event_id = db.get_cycle_event_id(int(cycle_id))
    if source_event_id is None:
        return 0
    weakened = 0
    for belief in db.list_beliefs_supported_by_event(source_event_id):
        db.weaken_belief(
            int(belief["id"]),
            factor,
            now,
            counterevidence_event_id=event_id,
        )
        weakened += 1
    return weakened


def apply_prediction_outcome(
    prediction: Any,
    outcome: str,
    evidence: str,
    born_at: float,
    *,
    now: float | None = None,
) -> dict | None:
    """Закрыть прогноз с исходом: обратная связь, вопрос при опровержении, правка убеждений.

    Возвращает событие потока для рассылки или None, если прогноз уже закрыт.
    """
    now = now or time.time()
    prediction_id = int(prediction["id"])
    if not db.resolve_prediction(prediction_id, outcome, evidence, now):
        return None
    names = _json_list(prediction["concept_names"])
    mind_time = format_mind_timestamp(born_at, now)
    content = f"Прогноз #{prediction_id}: {outcome}. Свидетельство: {evidence}"
    event_id = db.insert_stream_event(
        mind_time,
        "feedback",
        content,
        names,
        now,
        salience=1.0,
        reliability=0.95,
    )
    if outcome == "disconfirmed":
        db.create_inquiry(
            f"Почему был опровергнут прогноз: {prediction['statement']}?",
            names,
            0.95,
            "prediction_disconfirmed",
            now,
        )
        weakened = _weaken_beliefs_behind(
            prediction, DISCONFIRMED_BELIEF_FACTOR, event_id, now
        )
        logger.info(
            "Prediction %d disconfirmed; weakened %d belief(s)", prediction_id, weakened
        )
    return {
        "id": event_id,
        "mind_time": mind_time,
        "type": "feedback",
        "content": content,
        "concepts_involved": names,
        "created_at": now,
    }


def _evidence_is_quoted(evidence: str, observation: str) -> bool:
    """Свидетельство должно быть взято из наблюдения, а не пересказывать прогноз.

    Без этой проверки модель охотно закрывает весь запас прогнозов по одной
    лишь общности темы, подставляя вместо цитаты собственную интерпретацию.
    """
    tokens = _WORD_RE.findall(evidence.casefold())
    if not tokens:
        return False
    source = set(_WORD_RE.findall(observation.casefold()))
    hits = sum(1 for token in tokens if token in source)
    return hits / len(tokens) >= EVIDENCE_QUOTE_RATIO


async def resolve_predictions_with_observation(
    observation: str,
    source: str,
    concept_names: list[str],
    graph: Any,
    born_at: float,
) -> list[dict]:
    """Проверить открытые прогнозы пришедшим наблюдением."""
    now = time.time()
    candidates = db.list_pending_predictions_for_concepts(
        concept_names, now, limit=OBSERVATION_CANDIDATE_LIMIT
    )
    if not candidates:
        return []
    available_names = graph.relevant_names(concept_names, limit=36) or graph.all_names()
    td = get_time_display(born_at)
    result = await mind_engine.match_observation_to_predictions(
        observation,
        source,
        [dict(row) for row in candidates],
        available_names,
        td.mind_age_human,
        graph.edge_count(),
    )
    by_id = {int(row["id"]): row for row in candidates}
    events: list[dict] = []
    for match in result.get("matches") or []:
        if not isinstance(match, dict):
            continue
        try:
            prediction_id = int(match.get("prediction_id"))
        except (TypeError, ValueError):
            continue
        outcome = str(match.get("outcome") or "").strip().casefold()
        quote = " ".join(str(match.get("quote") or match.get("evidence") or "").split())
        reason = " ".join(str(match.get("reason") or "").split()).strip()
        evidence = f"«{quote}» {reason}".strip() if reason else quote
        prediction = by_id.get(prediction_id)
        if prediction is None or outcome not in {"confirmed", "disconfirmed"}:
            continue
        if not _evidence_is_quoted(quote, observation):
            logger.info(
                "Prediction %d left open: evidence is not taken from the observation",
                prediction_id,
            )
            continue
        payload = apply_prediction_outcome(
            prediction, outcome, evidence, born_at, now=now
        )
        if payload is not None:
            events.append(payload)
        if len(events) >= OBSERVATION_MAX_RESOLUTIONS:
            break
    if events:
        logger.info("Observation resolved %d prediction(s)", len(events))
    return events


def expire_predictions(born_at: float) -> list[dict]:
    """Закрыть прогнозы с вышедшим сроком и ослабить опирающиеся на них убеждения.

    Истечение — единственный сигнал ошибки, доступный без внешних наблюдений:
    он наказывает не неверное предсказание, а непроверяемое.
    """
    now = time.time()
    events: list[dict] = []
    for prediction in db.list_expired_predictions(now):
        prediction_id = int(prediction["id"])
        if not db.expire_prediction(prediction_id, now):
            continue
        names = _json_list(prediction["concept_names"])
        mind_time = format_mind_timestamp(born_at, now)
        content = (
            f"Прогноз #{prediction_id} истёк без проверки: {prediction['statement']} "
            f"Проверка не была применена: {prediction['test_method']}"
        )
        event_id = db.insert_stream_event(
            mind_time,
            "feedback",
            content,
            names,
            now,
            salience=0.7,
            reliability=0.6,
        )
        weakened = _weaken_beliefs_behind(
            prediction, EXPIRED_BELIEF_FACTOR, event_id, now
        )
        logger.info(
            "Prediction %d expired unverified; weakened %d belief(s)",
            prediction_id,
            weakened,
        )
        events.append({
            "id": event_id,
            "mind_time": mind_time,
            "type": "feedback",
            "content": content,
            "concepts_involved": names,
            "created_at": now,
        })
    return events


def maybe_select_connections(graph: Any) -> dict | None:
    """Отбор связей: затухание без подтверждений и конкуренция за место в окрестности.

    Плотный граф ничего не различает: пока каждый узел связан с каждым третьим,
    новое ребро делает его однороднее, а не структурнее. Отбор идёт с суточным
    шагом и ограниченным бюджетом, чтобы перестройку можно было наблюдать и
    остановить, а не обнаружить постфактум.
    """
    now = time.time()
    interval = _positive_env(
        "GRAPH_SELECTION_INTERVAL_SECONDS", GRAPH_SELECTION_INTERVAL_DEFAULT
    )
    raw = db.get_cognitive_state("last_graph_selection_at")
    try:
        last = float(raw) if raw else 0.0
    except ValueError:
        last = 0.0
    if now - last < interval:
        return None

    since = last if last else now - interval
    budget = _positive_env("GRAPH_SELECTION_BUDGET", GRAPH_SELECTION_BUDGET_DEFAULT)
    cap = _positive_env("GRAPH_DEGREE_CAP", GRAPH_DEGREE_CAP_DEFAULT)

    decayed = db.decay_connections(now, since, budget=budget)
    displaced = db.enforce_degree_cap(now, cap=cap, budget=budget)
    for a_id, b_id in [*decayed["archived"], *displaced]:
        graph.sync_connection(a_id, b_id)
    db.set_cognitive_state("last_graph_selection_at", str(now), now)

    result = {
        "weakened": decayed["weakened"],
        "archived_by_decay": len(decayed["archived"]),
        "displaced_by_cap": len(displaced),
        "active_edges": graph.edge_count(),
    }
    logger.info(
        "Graph selection: weakened=%d, archived=%d, displaced=%d, active edges=%d",
        result["weakened"],
        result["archived_by_decay"],
        result["displaced_by_cap"],
        result["active_edges"],
    )
    return result


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
