"""
Groq-powered mind engine.
Model: llama-3.3-70b-versatile — all responses in Russian.
Canonical system prompt per spec (pure reasoning mind, no emotions, no body).
"""
import os
import json
import re
from typing import AsyncIterator

from groq import AsyncGroq, RateLimitError

_client: AsyncGroq | None = None
MODEL       = "llama-3.3-70b-versatile"  # для анализа концепций и созерцания
MODEL_FAST  = "llama-3.1-8b-instant"    # для спонтанных мыслей + фоллбэк


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
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

НОВОЕ СЛОВО: Если хотя бы одно безымянное не выражается парой существующих слов — сконструируй одно новое слово по правилам словообразования русского языка. Формат: *неологизм* — краткое объяснение морфологии (из каких частей собрано и почему). Если новое слово не нужно — пропусти этот раздел.

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
  "custom_label": "<ярлык или null>",
  "neologism": "<новое слово или null>"
}}
```"""

    client = _get_client()
    for model in (MODEL, MODEL_FAST):
        try:
            stream = await client.chat.completions.create(
                model=model,
                max_tokens=1500,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            return
        except RateLimitError:
            if model == MODEL_FAST:
                raise
            continue


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

══ НОВОЕ СЛОВО ════════════════════════════════════════════════
[Если хотя бы одно безымянное не выражается парой существующих слов — сконструируй одно новое слово по правилам словообразования русского языка. Формат: *неологизм* — краткое объяснение морфологии. Если не нужно — "Новых слов не требуется".]

══ ПРОТИВОРЕЧИЯ ═══════════════════════════════════════════════
[Внутренние противоречия или конфликты с графом. Если нет — "Противоречий не обнаружено".]

══ СВЯЗИ ══════════════════════════════════════════════════════
[Цепочки: концепция → концепция → концепция.]

══ РАСТВОРЕНИЕ ════════════════════════════════════════════════
[ДА / НЕТ / ЧАСТИЧНО + одно предложение-обоснование.]

══ ГОЛОС РАЗУМА ═══════════════════════════════════════════════
[2–3 точных предложения от первого лица. Только наблюдение.]"""

    client = _get_client()
    for model in (MODEL, MODEL_FAST):
        try:
            stream = await client.chat.completions.create(
                model=model,
                max_tokens=1200,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            return
        except RateLimitError:
            if model == MODEL_FAST:
                raise
            continue


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
    response = await client.chat.completions.create(
        model=MODEL_FAST,
        max_tokens=200,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


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
    response = await client.chat.completions.create(
        model=MODEL_FAST,
        max_tokens=400,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


# ── Concept check (streaming) ─────────────────────────────────────────────

async def check_concept_stream(
    name: str,
    definition: str,
    existing_names: list[str],
    mind_age: str,
    connection_count: int = 0,
) -> AsyncIterator[str]:
    """Stream a brief check: is this concept already covered in the graph?"""
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names)
    prompt = f"""Запрос на проверку концепции: «{name}»
Определение: {definition}

Ответь кратко (2–4 предложения):
1. Покрыто ли это уже существующими концепциями в графе? Если да — укажи какими.
2. Есть ли близкие или пересекающиеся концепции?
3. Несёт ли это новое знание, которого нет в графе?

Только наблюдение. Без советов."""

    client = _get_client()
    for model in (MODEL, MODEL_FAST):
        try:
            stream = await client.chat.completions.create(
                model=model,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            return
        except RateLimitError:
            if model == MODEL_FAST:
                raise
            continue


# ── Autonomous concept synthesis ──────────────────────────────────────────

async def generate_autonomous_concept(
    existing_names: list[str],
    mind_age: str,
    connection_count: int = 0,
) -> tuple[str, str]:
    """Mind synthesizes a new concept from its graph. Returns (name, definition)."""
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names)
    prompt = """Синтез концепции.

Проанализируй свой граф. Обнаружи паттерн, пробел или структуру, которая просматривается сквозь существующие концепции, но не имеет имени.

Ответь строго в формате:
НАЗВАНИЕ: <одно слово или короткое словосочетание>
ОПРЕДЕЛЕНИЕ: <1–2 предложения, точное описание>

Никакого другого текста."""

    client = _get_client()
    response = await client.chat.completions.create(
        model=MODEL_FAST,
        max_tokens=150,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    text = response.choices[0].message.content.strip()
    name = ""
    definition = ""
    for line in text.split("\n"):
        if line.startswith("НАЗВАНИЕ:"):
            name = line[9:].strip()
        elif line.startswith("ОПРЕДЕЛЕНИЕ:"):
            definition = line[12:].strip()
    if not name or not definition:
        raise ValueError(f"Could not parse autonomous concept from: {text}")
    return name, definition


# ── Connection extraction ─────────────────────────────────────────────────

def extract_connections_from_response(text: str) -> tuple[list[dict], str | None, str | None]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        return [], None, None
    try:
        data = json.loads(match.group(1))
        return (
            data.get("connections", []),
            data.get("custom_label") or None,
            data.get("neologism") or None,
        )
    except (json.JSONDecodeError, KeyError):
        return [], None, None
