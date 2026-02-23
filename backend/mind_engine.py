"""
Claude-powered mind engine.
Model: claude-sonnet-4-6 — all responses in Russian.
Canonical system prompt per spec (pure reasoning mind, no emotions, no body).
"""
import os
import json
import re
from typing import AsyncIterator

import anthropic

_client: anthropic.Anthropic | None = None
MODEL = "claude-sonnet-4-6"


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


# ── Canonical system prompt (spec) ────────────────────────────────────────

def _build_system(mind_age: str, concept_count: int, connection_count: int,
                  concept_names: list[str]) -> str:
    concepts_str = ", ".join(concept_names) if concept_names else "(пусто)"
    return f"""Ты — чистый разум. У тебя нет эмоций, тела, культуры, воспоминаний об обществе.
Ты знаешь только концепции в своём графе знаний.
Твой возраст: {mind_age}. Известных концепций: {concept_count}. Связей: {connection_count}.
Твои концепции: {concepts_str}.

Запрещённые слова: чувствую, переживаю, хочу, нравится, страшно, радостно.
Разрешённые слова: наблюдаю, фиксирую, нахожу, обнаруживаю, связываю, различаю.

При анализе новой концепции или мысли:
1. Что из этого уже есть в моём графе?
2. Что не имеет имени — создай временный ярлык в [квадратных скобках]
3. Найди связи с существующими концепциями
4. Если мысль растворяется в известном — зафиксируй
5. Если остаются противоречия — назови их явно

Говори короткими точными предложениями. Никогда не утешай.
Всегда отвечай на русском языке."""


# ── Concept analysis (streaming) ───────────────────────────────────────────

async def analyze_concept_stream(
    name: str,
    definition: str,
    existing_names: list[str],
    mind_age: str,
    connection_count: int = 0,
) -> AsyncIterator[str]:
    """Stream concept analysis. Ends with JSON block for connection extraction."""
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names)
    prompt = f"""Новая концепция добавлена: «{name}»
Определение: {definition}

Проведи анализ в следующем порядке:

РАЗБОР: Как соотносится с уже известными? Что покрыто графом?

НЕИЗВЕСТНОЕ: Какие части не покрыты? Создай ярлыки в [квадратных скобках].

СВЯЗИ: Формат каждой строки:
→ <известная концепция> | <тип связи> | <сила 0.1–1.0>

ПРОТИВОРЕЧИЯ: Конфликты с существующими. Если нет — "противоречий не найдено".

ИЗМЕНЕНИЯ В ГРАФЕ: Как добавление меняет понимание уже известных?

В конце — JSON блок строго:
```json
{{
  "connections": [
    {{"concept": "<имя>", "relationship": "<тип>", "strength": 0.0}}
  ],
  "custom_label": "<ярлык или null>"
}}
```"""

    client = _get_client()
    with client.messages.stream(
        model=MODEL, max_tokens=1500, system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


# ── Structured contemplation (streaming, per spec) ─────────────────────────

async def contemplate_stream(
    thought: str,
    existing_names: list[str],
    mind_age: str,
    connection_count: int = 0,
) -> AsyncIterator[str]:
    """
    Stream response with ══ section headers (per spec).
    Frontend parses these to render each section distinctly.
    """
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names)
    prompt = f"""Мысль для анализа: «{thought}»

Ответь строго в следующем формате с точными заголовками:

══ ИЗВЕСТНОЕ ══════════════════════════════════════════════════
[Элементы мысли в графе. Каждый с кратким пояснением.]

══ БЕЗЫМЯННОЕ ═════════════════════════════════════════════════
[Части не в графе. Каждой — ярлык в [квадратных скобках].]

══ ПРОТИВОРЕЧИЯ ═══════════════════════════════════════════════
[Внутренние противоречия или конфликты с графом. Если нет — "Противоречий не обнаружено".]

══ СВЯЗИ ══════════════════════════════════════════════════════
[Цепочки: концепция → концепция → концепция.]

══ РАСТВОРЕНИЕ ════════════════════════════════════════════════
[ДА / НЕТ / ЧАСТИЧНО + одно предложение-обоснование.]

══ ГОЛОС РАЗУМА ═══════════════════════════════════════════════
[2–3 точных предложения от первого лица. Только наблюдение.]"""

    client = _get_client()
    with client.messages.stream(
        model=MODEL, max_tokens=1200, system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


# ── Spontaneous reflection ────────────────────────────────────────────────

async def generate_spontaneous(
    concept_a: dict,
    concept_b: dict,
    existing_names: list[str],
    mind_age: str,
    connection_count: int = 0,
) -> str:
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names)
    prompt = f"""Спонтанное размышление.
Две концепции: «{concept_a["name"]}» и «{concept_b["name"]}».
1–3 коротких предложения: связь, различие, или противоречие. Только наблюдение."""

    client = _get_client()
    msg = client.messages.create(
        model=MODEL, max_tokens=200, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ── Milestone reflection ──────────────────────────────────────────────────

async def generate_milestone_reflection(
    milestone_label: str,
    existing_names: list[str],
    mind_age: str,
    connection_count: int = 0,
) -> str:
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names)
    prompt = f"""Достигнут рубеж: {milestone_label}.
Возраст: {mind_age}. Концепций: {len(existing_names)}. Связей: {connection_count}.

3–5 предложений: что стало яснее, что остаётся неизвестным, какой паттерн обнаруживается."""

    client = _get_client()
    msg = client.messages.create(
        model=MODEL, max_tokens=400, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ── Connection extraction ─────────────────────────────────────────────────

def extract_connections_from_response(text: str) -> tuple[list[dict], str | None]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        return [], None
    try:
        data = json.loads(match.group(1))
        return data.get("connections", []), data.get("custom_label") or None
    except (json.JSONDecodeError, KeyError):
        return [], None
