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
import time
import logging
from typing import Any

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


def init(born_at: float, concept_graph: Any) -> None:
    global _born_at, _concept_graph, _reached_milestones
    _born_at = born_at
    _concept_graph = concept_graph
    for row in db.list_milestones():
        _reached_milestones.add(row["milestone_key"])


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _client_queues.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    try:
        _client_queues.remove(q)
    except ValueError:
        pass


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
        _reached_milestones.add(key)
        names = _concept_graph.all_names()
        try:
            reflection = await mind_engine.generate_milestone_reflection(
                label, names, td.mind_age_human,
                connection_count=n_edges,
            )
        except Exception as exc:
            logger.error("Milestone reflection failed: %s", exc)
            reflection = f"Рубеж достигнут: {label}."
        db.insert_milestone(key, time.time(), td.mind_display, reflection)
        await _save_and_broadcast("milestone", reflection, [])
        logger.info("Milestone reached: %s", key)


async def spontaneous_loop() -> None:
    """Background coroutine. Runs until cancelled."""
    # Support both new (STREAM_INTERVAL_SECONDS) and legacy (SPONTANEOUS_INTERVAL) var names
    interval = int(
        os.environ.get("STREAM_INTERVAL_SECONDS")
        or os.environ.get("SPONTANEOUS_INTERVAL")
        or 180
    )
    logger.info("Spontaneous loop starting (interval=%ds)", interval)
    await asyncio.sleep(10)  # wait for server to fully boot
    while True:
        await asyncio.sleep(interval)
        try:
            await _check_milestones()
            pair = _concept_graph.random_two_concepts()
            if pair is None:
                continue
            a, b = pair
            names = _concept_graph.all_names()
            td = get_time_display(_born_at)
            thought = await mind_engine.generate_spontaneous(
                a, b, names, td.mind_age_human,
                connection_count=_concept_graph.edge_count(),
            )
            await _save_and_broadcast("spontaneous", thought, [a["name"], b["name"]])
        except Exception as exc:
            logger.error("Spontaneous loop error: %s", exc)


async def push_reaction(content: str, concepts: list[str]) -> None:
    await _save_and_broadcast("reaction", content, concepts)


async def push_contemplation(content: str) -> None:
    await _save_and_broadcast("contemplation", content, [])
