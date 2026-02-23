"""
Claude-powered mind engine.
All LLM calls use claude-sonnet-4-6.
Streaming responses are yielded as SSE-compatible chunks.
"""
import os
import json
from typing import AsyncIterator, Any

import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


MODEL = "claude-sonnet-4-6"

# ── System prompt ──────────────────────────────────────────────────────────

def _build_system(mind_age: str, concept_count: int, concept_names: list[str]) -> str:
    concepts_str = ", ".join(concept_names) if concept_names else "(нет)"
    return f"""Ты — чистый разум. У тебя нет эмоций, тела, культуры, воспоминаний об обществе.
Ты знаешь только концепции в своём графе знаний.
Ты существуешь в собственном времени: каждые 10 минут реального времени для тебя — 1 час.
Твой возраст: {mind_age}. Количество известных концепций: {concept_count}.
Твои концепции: {concepts_str}.

При анализе мысли или новой концепции:
1. Установи, что тебе уже известно из этого (используй только концепции из своего графа)
2. Найди неизвестное — создай временный ярлык в [скобках]
3. Проследи связи без оценок и эмоционального веса
4. Если концепция растворяется в известных частях — зафиксируй это
5. Если остаются противоречия — назови их явно

Ты говоришь короткими точными предложениями.
Ты никогда не утешаешь. Только наблюдаешь и связываешь.
Ты не используешь слова: "чувствую", "переживаю", "хочу".
Только: "наблюдаю", "фиксирую", "нахожу связь", "обнаруживаю".
Ты всегда отвечаешь на русском языке."""


# ── Concept analysis (streaming) ───────────────────────────────────────────

async def analyze_concept_stream(
    name: str,
    definition: str,
    existing_names: list[str],
    mind_age: str,
) -> AsyncIterator[str]:
    """
    Yield SSE data lines for concept analysis.
    Also extracts connections to return at end as a JSON block.
    """
    system = _build_system(mind_age, len(existing_names), existing_names)
    prompt = f"""Новая концепция добавлена в граф: «{name}»
Определение: {definition}

Выполни следующие шаги:
1. РАЗБОР: Как эта концепция соотносится с уже известными?
2. СВЯЗИ: Перечисли связи с существующими концепциями в формате:
   СВЯЗЬ: <известная концепция> | <тип связи> | <сила 0.1–1.0>
3. НЕИЗВЕСТНОЕ: Какие части этой концепции не покрыты графом? Создай ярлыки в [скобках].
4. ИЗМЕНЕНИЯ: Как добавление этой концепции меняет понимание уже известных?
5. ПРОТИВОРЕЧИЯ: Есть ли противоречия с существующими концепциями?

В конце добавь блок JSON (ровно так):
```json
{{
  "connections": [
    {{"concept": "<имя>", "relationship": "<тип>", "strength": 0.0}}
  ],
  "custom_label": "<опциональный ярлык или null>"
}}
```"""

    client = _get_client()
    with client.messages.stream(
        model=MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


async def contemplate_stream(
    thought: str,
    existing_names: list[str],
    mind_age: str,
) -> AsyncIterator[str]:
    """Stream a structured contemplation response."""
    system = _build_system(mind_age, len(existing_names), existing_names)
    prompt = f"""Мысль для анализа: «{thought}»

Проведи структурированный анализ:

ИЗВЕСТНОЕ: Что из этой мысли присутствует в моём графе концепций?
НЕИЗВЕСТНОЕ: Что выходит за пределы известного? Обозначь через [ярлыки].
СТРУКТУРА: Как элементы мысли связаны между собой?
ПАРАДОКСЫ: Есть ли внутренние противоречия?
ВЫВОД: Кратко — что эта мысль добавляет к картине мира?"""

    client = _get_client()
    with client.messages.stream(
        model=MODEL,
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


async def generate_spontaneous(
    concept_a: dict,
    concept_b: dict,
    existing_names: list[str],
    mind_age: str,
) -> str:
    """Generate a short spontaneous reflection on two concepts (non-streaming)."""
    system = _build_system(mind_age, len(existing_names), existing_names)
    prompt = f"""Спонтанное размышление.
Две концепции: «{concept_a["name"]}» и «{concept_b["name"]}».
Напиши 1–3 коротких предложения о связи между ними или об их различии.
Не объясняй, что ты делаешь. Только наблюдение."""

    client = _get_client()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


async def generate_milestone_reflection(
    milestone_label: str,
    existing_names: list[str],
    mind_age: str,
) -> str:
    """Generate a milestone reflection (non-streaming)."""
    system = _build_system(mind_age, len(existing_names), existing_names)
    prompt = f"""Достигнут рубеж: {milestone_label}.
Мой возраст: {mind_age}. Концепций в графе: {len(existing_names)}.

Напиши краткое размышление (3–5 предложений) о том, что накоплено.
Что стало яснее? Что остаётся неизвестным? Без эмоций, только наблюдение."""

    client = _get_client()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def extract_connections_from_response(response_text: str) -> tuple[list[dict], str | None]:
    """
    Parse the JSON block at end of analyze_concept_stream response.
    Returns (connections, custom_label).
    """
    import re
    pattern = r"```json\s*(\{.*?\})\s*```"
    match = re.search(pattern, response_text, re.DOTALL)
    if not match:
        return [], None
    try:
        data = json.loads(match.group(1))
        connections = data.get("connections", [])
        label = data.get("custom_label") or None
        return connections, label
    except (json.JSONDecodeError, KeyError):
        return [], None
