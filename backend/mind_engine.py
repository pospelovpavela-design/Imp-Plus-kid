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
                  concept_names: list[str],
                  grounding_context: str | None = None) -> str:
    concepts_str = ", ".join(concept_names) if concept_names else "(пусто)"
    groundings = grounding_context.strip() if grounding_context else "Нет текстовых оснований опыта."
    return f"""Ты — чистый разум. У тебя нет эмоций, тела, культуры, воспоминаний об обществе.
Ты знаешь только концепции в своём графе знаний.
Твой возраст: {mind_age}. Известных концепций: {concept_count}. Связей: {connection_count}.
Твои концепции: {concepts_str}.

Текстовые основания опыта:
{groundings}

Если у концепции есть текстовое основание, отличай само слово от описанного в основании переживаемого опыта.
Если основания нет, называй концепцию незаземлённым ярлыком и не приписывай ей опытного содержания.

Запрещённые слова: чувствую, переживаю, хочу, нравится, страшно, радостно.
Разрешённые слова: наблюдаю, фиксирую, нахожу, обнаруживаю, связываю, различаю.

При анализе новой концепции или мысли:
1. Что из этого уже есть в моём графе?
2. Что не имеет имени — создай временный ярлык в [квадратных скобках]. Не создавай ярлык для "определения" или "понимания" уже известной концепции.
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
    grounding_context: str | None = None,
) -> AsyncIterator[str]:
    """Stream concept analysis. Ends with JSON block for connection extraction."""
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names,
                           grounding_context)
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
    grounding_context: str | None = None,
) -> AsyncIterator[str]:
    """
    Stream response with ══ section headers (per spec).
    Frontend parses these to render each section distinctly.
    """
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names,
                           grounding_context)
    prompt = f"""Мысль для анализа: «{thought}»

Ответь строго в следующем формате с точными заголовками:

══ ИЗВЕСТНОЕ ══════════════════════════════════════════════════
[Элементы мысли в графе. Если есть текстовое основание, используй его содержание как основание пояснения, а не называй его внешней справкой.]

══ БЕЗЫМЯННОЕ ═════════════════════════════════════════════════
[Только части мысли, которых действительно нет в графе и в текстовых основаниях. Каждой — ярлык в [квадратных скобках]. Если всё покрыто известным или основанием, напиши: "Нет". Не создавай ярлыки вида [Определение ...], [Понимание ...], если речь о раскрытии уже известной концепции.]

══ НОВОЕ СЛОВО ════════════════════════════════════════════════
[Если хотя бы одно безымянное не выражается парой существующих слов — сконструируй одно новое слово по правилам словообразования русского языка. Формат: *неологизм* — краткое объяснение морфологии. Если не нужно — "Новых слов не требуется".]

══ ПРОТИВОРЕЧИЯ ═══════════════════════════════════════════════
[Внутренние противоречия или конфликты с графом. Если нет — "Противоречий не обнаружено".]

══ СВЯЗИ ══════════════════════════════════════════════════════
[Цепочки: концепция → концепция → концепция. Используй только русские имена концепций из графа; не вставляй английские слова.]

══ РАСТВОРЕНИЕ ════════════════════════════════════════════════
[ДА / НЕТ / ЧАСТИЧНО + одно предложение-обоснование.]

══ ГОЛОС РАЗУМА ═══════════════════════════════════════════════
[2–3 точных предложения от первого лица. Только наблюдение.]

Не добавляй JSON, markdown-код, служебные блоки или технические данные после ответа.
Ответ должен закончиться секцией "ГОЛОС РАЗУМА"."""

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
    grounding_context: str | None = None,
) -> str:
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names,
                           grounding_context)
    names_str = ", ".join(existing_names[:20]) if existing_names else "(пусто)"
    prompt = f"""Спонтанное размышление.
Два концепта: «{concept_a["name"]}» и «{concept_b["name"]}».
1–3 предложения: связь, различие или противоречие. Только наблюдение.

В конце — JSON строго в этом формате:
```json
{{
  "connections": [
    {{"concept": "имя_из_списка", "relationship": "тип_связи", "strength": 0.7}}
  ],
  "custom_label": null,
  "neologism": null
}}
```
strength: 0.1–1.0. Имена только из: {names_str}"""

    client = _get_client()
    response = await client.chat.completions.create(
        model=MODEL_FAST,
        max_tokens=500,
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
    grounding_context: str | None = None,
) -> str:
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names,
                           grounding_context)
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
    grounding_context: str | None = None,
) -> AsyncIterator[str]:
    """Stream a brief check: is this concept already covered in the graph?"""
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names,
                           grounding_context)
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
    grounding_context: str | None = None,
) -> tuple[str, str]:
    """Mind synthesizes a new concept from its graph. Returns (name, definition)."""
    system = _build_system(mind_age, len(existing_names), connection_count, existing_names,
                           grounding_context)
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
        line = line.strip()
        if not line:
            continue
        if re.match(r"^НАЗВАНИЕ\s*[:：]", line):
            name = re.sub(r"^НАЗВАНИЕ\s*[:：]\s*", "", line).strip()
        elif re.match(r"^ОПРЕДЕЛЕНИЕ\s*[:：]", line):
            definition = re.sub(r"^ОПРЕДЕЛЕНИЕ\s*[:：]\s*", "", line).strip()
    # Fallback: if format ignored — treat first non-empty line as name, second as definition
    if not name or not definition:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) >= 2:
            # Strip any "WORD:" prefix the model might have used
            name = re.sub(r"^[А-ЯA-Z][А-ЯA-Z\-]+\s*[:：]\s*", "", lines[0]).strip() or lines[0]
            definition = re.sub(r"^[А-ЯA-Z][А-ЯA-Z\-]+\s*[:：]\s*", "", lines[1]).strip() or lines[1]
        elif lines:
            name = lines[0]
            definition = lines[0]
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
        connections = data.get("connections", [])
        if not isinstance(connections, list):
            connections = []
        custom_label = data.get("custom_label") or None
        if isinstance(custom_label, list):
            custom_label = custom_label[0] if custom_label else None
        neologism = data.get("neologism") or None
        if isinstance(neologism, list):
            neologism = neologism[0] if neologism else None
        # Reject placeholder values the model sometimes returns verbatim
        if neologism in ("null", "none", "нет", "не нужно", "не требуется"):
            neologism = None
        return connections, custom_label, neologism
    except (json.JSONDecodeError, KeyError):
        return [], None, None
