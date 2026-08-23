"""
Stream engine — manages the live thought feed.

Responsibilities:
  1. Background loop: run an evidence-gated cognitive cycle
  2. Broadcast: push any new event to all connected SSE clients
  3. Milestone checker: time-based + count-based milestones → trigger reflections
"""
import asyncio
import json
import os
import time
import logging
from typing import Any

from openai import RateLimitError

import cognitive_engine
import daily_insight_engine
import db
import mind_engine
from time_engine import (
    format_mind_timestamp, check_new_milestones, check_count_milestones, get_time_display,
)

logger = logging.getLogger("stream_engine")

_client_queues: list[asyncio.Queue] = []
_reached_milestones: set[str] = set()

# Filled in on startup by main.py
_born_at: float = 0.0
_concept_graph: Any = None

def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        logger.warning("Invalid %s; using %d", name, default)
        return default
    if value <= 0:
        logger.warning("Invalid %s; using %d", name, default)
        return default
    return value


def _record_cycle_health(ok: bool, error: str | None = None) -> None:
    """Отметить исход цикла, чтобы молчание было видно снаружи.

    Обе остановки мышления в августе выглядели одинаково: живой сервис, сайт
    отдаёт 200, и единственный след аварии — строка в журнале на сервере.
    """
    now = time.time()
    if ok:
        db.set_cognitive_state("last_cycle_at", str(now), now)
        db.set_cognitive_state("last_cycle_error", "", now)
        return
    db.set_cognitive_state("last_cycle_error", " ".join(str(error or "").split())[:500], now)
    db.set_cognitive_state("last_cycle_error_at", str(now), now)


def _rate_limit_backoff(failures: int, initial: int, maximum: int) -> int:
    """Return a bounded exponential delay for consecutive 429 responses."""
    exponent = max(0, min(failures - 1, 30))
    return min(maximum, initial * (2 ** exponent))


def init(born_at: float, concept_graph: Any) -> None:
    global _born_at, _concept_graph, _reached_milestones
    _born_at = born_at
    _concept_graph = concept_graph
    for row in db.list_milestones():
        _reached_milestones.add(row["milestone_key"])
    cognitive_engine.initialize()


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _client_queues.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    try:
        _client_queues.remove(q)
    except ValueError:
        pass


def _build_grounding_context(names: list[str], limit: int = 6) -> str:
    rows = db.find_groundings_for_concept_names(names, limit=limit)
    if not rows:
        return ""
    parts = []
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["concept_name"], []).append(row)
    for concept_name, concept_rows in grouped.items():
        if len(concept_rows) > 1:
            parts.append(
                f"- Концепция «{concept_name}» имеет несколько материалов опыта. "
                "Сравни их: найди общее ядро, различия, напряжения и собственное рабочее определение."
            )
        for row in concept_rows:
            note = f" Привязка: {row['note']}." if row["note"] else ""
            excerpt = row["excerpt"].strip().replace("\n", " ")
            if len(excerpt) > 1200:
                excerpt = excerpt[:1197].rstrip() + "..."
            parts.append(
                f"  - Материал для «{concept_name}».{note} "
                f"Переработай его через граф, без пересказа источника: «{excerpt}»"
            )
    return "\n".join(parts)


async def broadcast(event: dict) -> None:
    msg = json.dumps(event, ensure_ascii=False)
    dead = []
    for q in _client_queues:
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _client_queues.remove(q)


async def _save_and_broadcast(
    event_type: str,
    content: str,
    concepts: list[str],
    *,
    salience: float = 0.5,
    reliability: float = 0.5,
    consolidated: bool = False,
    cycle_id: int | None = None,
) -> int:
    mind_time = format_mind_timestamp(_born_at)
    now = time.time()
    eid = db.insert_stream_event(
        mind_time,
        event_type,
        content,
        concepts,
        now,
        salience=salience,
        reliability=reliability,
        consolidated=consolidated,
        cycle_id=cycle_id,
    )
    await broadcast({
        "id": eid,
        "mind_time": mind_time,
        "type": event_type,
        "content": content,
        "concepts_involved": concepts,
        "created_at": now,
    })
    return eid


async def _check_milestones() -> None:
    """Check both time-based and count-based milestones."""
    td = get_time_display(_born_at)
    n_concepts = _concept_graph.node_count()
    n_edges = _concept_graph.edge_count()

    new_time  = check_new_milestones(_born_at, _reached_milestones)
    new_count = check_count_milestones(n_concepts, n_edges, _reached_milestones)

    for key, label in new_time + new_count:
        names = _concept_graph.all_names()
        try:
            grounding_context = _build_grounding_context(names)
            reflection = await mind_engine.generate_milestone_reflection(
                label, names, td.mind_age_human,
                connection_count=n_edges,
                grounding_context=grounding_context,
            )
        except RateLimitError:
            raise
        except Exception as exc:
            logger.error("Milestone reflection failed: %s", exc)
            reflection = f"Рубеж достигнут: {label}."
        _reached_milestones.add(key)
        db.insert_milestone(key, time.time(), td.mind_display, reflection)
        await _save_and_broadcast("milestone", reflection, [])
        logger.info("Milestone reached: %s", key)


async def spontaneous_loop() -> None:
    """Background coroutine. Runs until cancelled."""
    # Support both new (STREAM_INTERVAL_SECONDS) and legacy (SPONTANEOUS_INTERVAL) var names
    requested_interval = _positive_int_env(
        "STREAM_INTERVAL_SECONDS",
        _positive_int_env("SPONTANEOUS_INTERVAL", 180),
    )
    minimum_interval = _positive_int_env("COGNITIVE_MIN_INTERVAL_SECONDS", 1800)
    interval = max(requested_interval, minimum_interval)
    backoff_initial = _positive_int_env("RATE_LIMIT_BACKOFF_INITIAL_SECONDS", 900)
    backoff_max = max(
        backoff_initial,
        _positive_int_env("RATE_LIMIT_BACKOFF_MAX_SECONDS", 21600),
    )
    rate_limit_failures = 0
    next_delay = interval
    logger.info(
        "Cognitive loop starting (interval=%ds, rate-limit backoff=%ds..%ds)",
        interval,
        backoff_initial,
        backoff_max,
    )
    db.set_cognitive_state("cycle_interval_seconds", str(interval), time.time())
    await asyncio.sleep(10)  # wait for server to fully boot
    while True:
        await asyncio.sleep(next_delay)
        next_delay = interval
        try:
            await _check_milestones()
            event = await cognitive_engine.run_cycle(_concept_graph, _born_at)
            _record_cycle_health(True)
            if event is not None:
                await broadcast(event)
                logger.info(
                    "Cognitive cycle completed: verdict=%s, accepted relations=%d",
                    event["verdict"],
                    event["accepted_relations"],
                )
            for expired in cognitive_engine.expire_predictions(_born_at):
                await broadcast(expired)
            cognitive_engine.maybe_select_connections(_concept_graph)
            named = await cognitive_engine.maybe_create_concept(_concept_graph, _born_at)
            if named is not None:
                await broadcast(named)
            consolidation = await cognitive_engine.maybe_consolidate(
                _concept_graph,
                _born_at,
            )
            if consolidation is not None:
                await broadcast(consolidation)
            daily_result = await daily_insight_engine.maybe_generate_today(_born_at)
            if daily_result is not None:
                insight, created = daily_result
                if created:
                    daily_event = daily_insight_engine.stream_event_payload(insight)
                    if daily_event is not None:
                        await broadcast(daily_event)
                    logger.info("Daily insight generated for %s", insight["local_date"])
            rate_limit_failures = 0
        except RateLimitError as exc:
            _record_cycle_health(False, f"Лимит запросов к модели: {exc}")
            rate_limit_failures += 1
            next_delay = _rate_limit_backoff(
                rate_limit_failures,
                backoff_initial,
                backoff_max,
            )
            logger.warning(
                "Model rate limit reached; pausing cognition for %ds "
                "(consecutive failures=%d)",
                next_delay,
                rate_limit_failures,
            )
        except Exception as exc:
            _record_cycle_health(False, str(exc))
            logger.exception("Cognitive loop error: %s", exc)


async def push_reaction(content: str, concepts: list[str]) -> None:
    await _save_and_broadcast(
        "reaction",
        content,
        concepts,
        salience=0.75,
        reliability=0.65,
    )


async def push_contemplation(content: str) -> None:
    await _save_and_broadcast(
        "contemplation",
        content,
        [],
        salience=0.8,
        reliability=0.65,
    )


async def push_external_event(
    event_type: str,
    content: str,
    concepts: list[str],
    *,
    salience: float,
    reliability: float,
) -> int:
    if event_type not in {"observation", "feedback"}:
        raise ValueError("Unsupported external event type")
    return await _save_and_broadcast(
        event_type,
        content,
        concepts,
        salience=salience,
        reliability=reliability,
    )
