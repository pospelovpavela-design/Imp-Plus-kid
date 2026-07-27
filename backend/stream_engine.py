"""
Stream engine — manages the live thought feed.

Responsibilities:
  1. Background loop: every STREAM_INTERVAL_SECONDS generate a spontaneous thought
  2. Broadcast: push any new event to all connected SSE clients
  3. Milestone checker: time-based + count-based milestones → trigger reflections
"""
import asyncio
import json
import os
import re
import time
import logging
from typing import Any

from groq import RateLimitError

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

# Autonomous concept creation — once per 24 real hours
_last_autonomous_time: float = 0.0
AUTONOMOUS_INTERVAL = 86400  # seconds


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


def _rate_limit_backoff(failures: int, initial: int, maximum: int) -> int:
    """Return a bounded exponential delay for consecutive Groq 429 responses."""
    exponent = max(0, min(failures - 1, 30))
    return min(maximum, initial * (2 ** exponent))


def init(born_at: float, concept_graph: Any) -> None:
    global _born_at, _concept_graph, _reached_milestones, _last_autonomous_time
    _born_at = born_at
    _concept_graph = concept_graph
    for row in db.list_milestones():
        _reached_milestones.add(row["milestone_key"])
    last_auto = db.get_last_autonomous_time()
    if last_auto is not None:
        _last_autonomous_time = last_auto


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


async def _save_and_broadcast(event_type: str, content: str, concepts: list[str]) -> None:
    mind_time = format_mind_timestamp(_born_at)
    now = time.time()
    eid = db.insert_stream_event(mind_time, event_type, content, concepts, now)
    await broadcast({
        "id": eid,
        "mind_time": mind_time,
        "type": event_type,
        "content": content,
        "concepts_involved": concepts,
        "created_at": now,
    })


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


async def _maybe_create_autonomous_concept() -> None:
    """Create one autonomous concept per day if enough concepts exist."""
    global _last_autonomous_time
    now = time.time()
    if now - _last_autonomous_time < AUTONOMOUS_INTERVAL:
        return
    if _concept_graph.node_count() < 3:
        return

    td = get_time_display(_born_at)
    names = _concept_graph.all_names()
    try:
        grounding_context = _build_grounding_context(names)
        name, definition = await mind_engine.generate_autonomous_concept(
            names, td.mind_age_human,
            connection_count=_concept_graph.edge_count(),
            grounding_context=grounding_context,
        )
        if db.concept_exists(name):
            _last_autonomous_time = now
            return

        cid = _concept_graph.add_concept(
            name, definition, td.mind_display, now, is_autonomous=True
        )
        _last_autonomous_time = now

        # Analyze to build connections (collect full text, no streaming needed)
        full_text = ""
        async for chunk in mind_engine.analyze_concept_stream(
            name, definition, names, td.mind_age_human,
            connection_count=_concept_graph.edge_count(),
            grounding_context=grounding_context,
        ):
            full_text += chunk

        _concept_graph.add_processing_log(cid, full_text)
        connections, custom_label, neologism = mind_engine.extract_connections_from_response(full_text)
        for conn in connections:
            other = db.get_concept_by_name(conn.get("concept", ""))
            if other:
                _concept_graph.add_connection(
                    cid, other["id"],
                    conn.get("relationship", ""),
                    float(conn.get("strength", 0.5)),
                )
        label = custom_label or neologism
        if label:
            _concept_graph.set_custom_label(cid, label)
        if neologism:
            db.insert_neologism(neologism, full_text[:300], "autonomous", cid,
                                td.mind_display, time.time())

        _last_autonomous_time = now
        await _save_and_broadcast(
            "autonomous",
            f"Разум самостоятельно синтезировал концепцию «{name}»: {definition}",
            [name],
        )
        logger.info("Autonomous concept created: %s", name)
    except RateLimitError:
        raise
    except Exception as exc:
        logger.error("Autonomous concept creation failed: %s", exc)
        _last_autonomous_time = now  # Prevent rapid retries on error


async def spontaneous_loop() -> None:
    """Background coroutine. Runs until cancelled."""
    # Support both new (STREAM_INTERVAL_SECONDS) and legacy (SPONTANEOUS_INTERVAL) var names
    interval = _positive_int_env(
        "STREAM_INTERVAL_SECONDS",
        _positive_int_env("SPONTANEOUS_INTERVAL", 180),
    )
    backoff_initial = _positive_int_env("RATE_LIMIT_BACKOFF_INITIAL_SECONDS", 900)
    backoff_max = max(
        backoff_initial,
        _positive_int_env("RATE_LIMIT_BACKOFF_MAX_SECONDS", 21600),
    )
    rate_limit_failures = 0
    next_delay = interval
    logger.info(
        "Spontaneous loop starting (interval=%ds, rate-limit backoff=%ds..%ds)",
        interval,
        backoff_initial,
        backoff_max,
    )
    await asyncio.sleep(10)  # wait for server to fully boot
    while True:
        await asyncio.sleep(next_delay)
        next_delay = interval
        try:
            await _check_milestones()
            await _maybe_create_autonomous_concept()
            pair = _concept_graph.random_two_concepts()
            if pair is None:
                continue
            a, b = pair
            names = _concept_graph.all_names()
            td = get_time_display(_born_at)
            thought = await mind_engine.generate_spontaneous(
                a, b, names, td.mind_age_human,
                connection_count=_concept_graph.edge_count(),
                grounding_context=_build_grounding_context([a["name"], b["name"]]),
            )

            # Apply connections found in this spontaneous thought to the graph
            connections, _label, neologism = mind_engine.extract_connections_from_response(thought)
            if neologism:
                db.insert_neologism(neologism, thought[:300], "spontaneous", None,
                                    td.mind_display, time.time())
            applied = 0
            if connections:
                for conn in connections:
                    rel = conn.get("relationship", "")
                    strength = float(conn.get("strength", 0))
                    # Skip unfilled template values
                    if rel in ("link", "<тип связи>", "") or strength <= 0.0:
                        continue
                    other = db.get_concept_by_name(conn.get("concept", ""))
                    if other and other["id"] != a["id"]:
                        _concept_graph.add_connection(
                            a["id"], other["id"],
                            rel,
                            strength,
                        )
                        applied += 1
            # Fallback: if LLM gave no parseable JSON, connect A↔B directly
            if applied == 0:
                b_row = db.get_concept_by_name(b["name"])
                if b_row and b_row["id"] != a["id"]:
                    _concept_graph.add_connection(
                        a["id"], b_row["id"],
                        "спонтанная связь",
                        0.3,
                    )
                    applied += 1
            logger.info("Spontaneous thought: %s↔%s, edges applied: %d", a["name"], b["name"], applied)

            # Strip JSON before broadcasting — handles both ```json...``` and raw objects
            clean_thought = re.sub(r"```json[\s\S]*?```", "", thought, flags=re.DOTALL)
            # Strip raw JSON objects with up to 2 levels of nesting ({...{...}...})
            clean_thought = re.sub(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', "", clean_thought)
            # Strip leftover "JSON:" / "JSON" markers
            clean_thought = re.sub(r'(?i)\bJSON[:\s]*', "", clean_thought)
            clean_thought = clean_thought.strip()
            await _save_and_broadcast("spontaneous", clean_thought, [a["name"], b["name"]])
            rate_limit_failures = 0
        except RateLimitError:
            rate_limit_failures += 1
            next_delay = _rate_limit_backoff(
                rate_limit_failures,
                backoff_initial,
                backoff_max,
            )
            logger.warning(
                "Groq rate limit reached; pausing spontaneous generation for %ds "
                "(consecutive failures=%d)",
                next_delay,
                rate_limit_failures,
            )
        except Exception as exc:
            logger.error("Spontaneous loop error: %s", exc)


async def push_reaction(content: str, concepts: list[str]) -> None:
    await _save_and_broadcast("reaction", content, concepts)


async def push_contemplation(content: str) -> None:
    await _save_and_broadcast("contemplation", content, [])
