"""Retrieval and self-context for persistent cognitive cycles."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import re
import time

import db


_WORD_RE = re.compile(r"[^\W_]{3,}", flags=re.UNICODE)

# Старый спонтанный поток — 96% всех событий и почти весь шум. Он остаётся в
# истории и в полнотекстовом поиске, но свидетельством для критика не служит:
# критик, читая свободную ассоциацию, справедливо отвечает «доказательств нет».
EVIDENCE_TYPES: tuple[str, ...] = (
    "cognitive",
    "consolidation",
    "observation",
    "feedback",
    "contemplation",
    "reaction",
    "milestone",
)


# Эпизоды, где концепция фокуса лишь упомянута словом, а не помечена
WORDED_LIMIT = 3
# Эпизоды, не связанные с фокусом вовсе: только чтобы дополнить выборку
BACKGROUND_LIMIT = 2


def _evidence_types() -> tuple[str, ...] | None:
    """None означает «брать события любого типа»."""
    flag = os.environ.get("MEMORY_INCLUDE_SPONTANEOUS", "").strip().casefold()
    return None if flag in {"1", "true", "yes"} else EVIDENCE_TYPES


@dataclass
class MemoryContext:
    event_ids: list[int]
    text: str
    concept_names: list[str]


def _tokens(text: str, limit: int = 10) -> list[str]:
    seen: set[str] = set()
    result = []
    for token in _WORD_RE.findall(text.casefold()):
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
        if len(result) >= limit:
            break
    return result


def _concepts(raw: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def retrieve_memories(
    query: str,
    concept_names: list[str],
    *,
    limit: int = 8,
    now: float | None = None,
) -> MemoryContext:
    now = now or time.time()
    terms = list(dict.fromkeys([*concept_names, *_tokens(query)]))
    types = _evidence_types()
    candidates = db.search_memory_events(terms, limit=max(40, limit * 5), types=types)
    by_id = {int(row["id"]): row for row in candidates}
    matched_ids = set(by_id)
    for row in db.list_recent_high_quality_events(limit=20, types=types):
        by_id.setdefault(int(row["id"]), row)

    focus = {name.casefold() for name in concept_names}
    query_tokens = set(_tokens(query, limit=16))
    tagged: list[tuple[float, dict]] = []
    worded: list[tuple[float, dict]] = []
    background: list[tuple[float, dict]] = []
    seen_content: set[str] = set()
    for row in by_id.values():
        content = str(row["content"]).strip()
        if not content:
            continue
        fingerprint = " ".join(content.casefold().split())[:300]
        if fingerprint in seen_content:
            continue
        seen_content.add(fingerprint)

        event_concepts = {name.casefold() for name in _concepts(row["concepts_involved"])}
        overlap = len(focus & event_concepts)
        reliability = float(row.get("reliability") or 0.5)
        salience = float(row.get("salience") or 0.5)
        age_days = max(0.0, (now - float(row["created_at"])) / 86400)
        recency = math.exp(-age_days / 30)
        lexical_rank = abs(float(row.get("lexical_rank") or 0.0))
        lexical = 1 / (1 + lexical_rank)
        type_bonus = 0.2 if row["type"] in {
            "cognitive", "contemplation", "observation", "feedback", "consolidation"
        } else 0.0
        score = (
            min(0.6, overlap * 0.3)
            + reliability * 0.35
            + salience * 0.2
            + recency * 0.15
            + lexical * 0.15
            + type_bonus
        )
        # Три уровня, а не два. Эпизод, помеченный концепцией фокуса, говорит
        # о ней; эпизод, где слово лишь произнесено, — нет. Почти каждое
        # наблюдение начинается с «В памяти зафиксировано», и по слову «память»
        # выборка целиком уходила в старую тему.
        mentions = int(row["id"]) in matched_ids or bool(
            query_tokens & set(_tokens(content, limit=40))
        )
        if overlap > 0:
            tagged.append((score, row))
        elif mentions:
            worded.append((score, row))
        else:
            background.append((score, row))

    for bucket in (tagged, worded, background):
        bucket.sort(key=lambda item: item[0], reverse=True)

    chosen = tagged[:limit]
    chosen += worded[: max(0, min(WORDED_LIMIT, limit - len(chosen)))]
    # Постороннее — только если по фокусу не нашлось вообще ничего. Показать
    # скудную память честнее, чем добить её до полного списка чужими эпизодами.
    if not chosen:
        chosen = background[:BACKGROUND_LIMIT]
    selected = [row for _, row in chosen[:limit]]
    lines = []
    event_ids = []
    mentioned: dict[str, int] = {}
    for row in selected:
        event_ids.append(int(row["id"]))
        for name in _concepts(row["concepts_involved"]):
            mentioned[name] = mentioned.get(name, 0) + 1
        content = " ".join(str(row["content"]).split())
        if len(content) > 600:
            content = content[:597].rstrip() + "..."
        lines.append(
            f"- Память #{row['id']} [{row['type']}; {row['mind_time']}]: {content}"
        )

    observations = db.list_external_observations(limit=8)
    query_tokens = set(_tokens(query, limit=16))
    for row in observations:
        obs_concepts = {name.casefold() for name in _concepts(row["concept_names"])}
        obs_tokens = set(_tokens(row["content"], limit=40))
        if focus & obs_concepts or query_tokens & obs_tokens:
            content = " ".join(str(row["content"]).split())
            lines.append(
                f"- Внешнее наблюдение #{row['id']} "
                f"(надёжность {float(row['reliability']):.2f}): {content[:600]}"
            )

    for row in observations:
        for name in _concepts(row["concept_names"]):
            mentioned[name] = mentioned.get(name, 0) + 1

    return MemoryContext(
        event_ids=event_ids,
        text="\n".join(lines) if lines else "Релевантных эпизодов памяти не найдено.",
        concept_names=[
            name for name, _ in sorted(mentioned.items(), key=lambda item: -item[1])
        ],
    )


def initialize_self_model(now: float | None = None) -> None:
    now = now or time.time()
    entries = {
        "model_dependency": (
            "Мои языковые выводы вычисляются внешней моделью; без API генерация прекращается.",
            1.0,
            "Системная архитектура.",
        ),
        "sensory_limits": (
            "У меня нет прямых сенсоров. Внешний опыт появляется только через явно записанные наблюдения и основания.",
            1.0,
            "Системная архитектура.",
        ),
        "memory_limits": (
            "В рабочий контекст попадает только небольшая выборка релевантной памяти; отсутствие воспоминания не доказывает отсутствие события.",
            0.95,
            "Ограничение retrieval-контекста.",
        ),
        "fallibility": (
            "Сгенерированная гипотеза может быть ложной и не меняет знания до отдельной критической проверки.",
            1.0,
            "Правило когнитивного цикла.",
        ),
        "agency_limits": (
            "Я могу формировать вопросы и прогнозы, но внешнее действие и проверка требуют наблюдения оператора или подключённого инструмента.",
            1.0,
            "Доступные интерфейсы.",
        ),
    }
    for key, (value, confidence, evidence) in entries.items():
        db.upsert_self_model_entry(key, value, confidence, evidence, now)


def build_self_context() -> str:
    metrics = db.get_cognitive_metrics()
    entries = db.list_self_model_entries()
    facts = [
        f"- {row['value']} (уверенность {float(row['confidence']):.2f})"
        for row in entries
    ]
    facts.extend([
        f"- Активных концепций: {metrics['concepts']}; активных связей: {metrics['active_edges']}.",
        f"- Плотность активного графа: {metrics['active_graph_density']:.3f}.",
        f"- Доля заземлённых концепций: {metrics['grounding_coverage']:.3f}.",
        f"- Открытых внутренних вопросов: {metrics['open_inquiries']}.",
        f"- Непроверенных прогнозов: {metrics['pending_predictions']}.",
    ])
    return "\n".join(facts)
