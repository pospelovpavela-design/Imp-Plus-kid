"""
FastAPI application — entry point.
Run with:  cd backend && uvicorn main:app --reload --port 8000

Auth policy (per spec):
  - Auth REQUIRED  → POST /concept/add, POST /contemplate
  - Auth NOT needed → all GET endpoints (read-only public access)
"""
import asyncio
import json
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import db
import stream_engine
import mind_engine
import auth
from concept_graph import ConceptGraph
from time_engine import get_time_display, format_mind_timestamp

# ── App state ──────────────────────────────────────────────────────────────

graph: ConceptGraph | None = None
MAX_GROUNDING_EXCERPT_CHARS = 20_000


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    db.init_db()

    state = db.get_mind_state()
    born_at: float

    if state is None:
        born_at = time.time()
        db.create_mind_state(born_at, "IMPLUS")
        print(f"[IMPLUS] First launch — mind born at {born_at}")
        graph = ConceptGraph(born_at)
        graph.bootstrap_seeds()
    else:
        born_at = state["born_at"]
        print(f"[IMPLUS] Resuming mind born at {born_at}")
        graph = ConceptGraph(born_at)

    stream_engine.init(born_at, graph)
    task = asyncio.create_task(stream_engine.spontaneous_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="IMPLUS — Isolated Mind", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000",
                   "https://pockily-trimorphic-hiroko.ngrok-free.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth (login only) ──────────────────────────────────────────────────────

class LoginBody(BaseModel):
    password: str


@app.post("/auth/login")
def login(body: LoginBody):
    if not auth.verify_password(body.password):
        raise HTTPException(status_code=401, detail="Неверный пароль")
    return {"token": auth.create_token()}


# ── Time — PUBLIC ──────────────────────────────────────────────────────────

@app.get("/time")
def get_time():
    state = db.get_mind_state()
    td = get_time_display(state["born_at"])
    return {
        "mind_display": td.mind_display,
        "mind_age_human": td.mind_age_human,
        "mind_total_seconds": td.mind_total_seconds,
        "mind_days": td.mind_days,
        "mind_hours": td.mind_hours,
        "mind_minutes": td.mind_minutes,
        "mind_seconds": td.mind_seconds,
        "real_display": td.real_display,
        "real_total_seconds": td.real_total_seconds,
        "ratio": td.ratio,
        "born_at": state["born_at"],
    }


@app.get("/time/milestones")
def get_milestones():
    return [dict(r) for r in db.list_milestones()]


# ── Concept — reads PUBLIC, writes protected ───────────────────────────────

class AddConceptBody(BaseModel):
    name: str
    definition: str


class GroundingExcerptBody(BaseModel):
    title: str
    excerpt: str
    author: str | None = None
    source: str | None = None
    concept_names: list[str] = Field(default_factory=list)
    note: str | None = None


class ExternalObservationBody(BaseModel):
    content: str
    source: str
    concept_names: list[str] = Field(default_factory=list)
    reliability: float = 0.8


class PredictionResolutionBody(BaseModel):
    outcome: str
    evidence: str


def _grounding_row_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "author": row["author"],
        "source": row["source"],
        "excerpt": row["excerpt"],
        "note": row["note"] if "note" in row.keys() else None,
        "mind_time": row["mind_time"],
        "created_at": row["created_at"],
        "concept_name": row["concept_name"] if "concept_name" in row.keys() else None,
        "concept_names": row["concept_names"] if "concept_names" in row.keys() else None,
    }


def _concept_names_in_text(text: str, limit: int = 12) -> list[str]:
    text_lower = text.lower()
    found = []
    for name in graph.all_names():
        if name.lower() in text_lower:
            found.append(name)
            if len(found) >= limit:
                break
    return found


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


def _working_definition_row_to_dict(row):
    return {
        "id": row["id"],
        "concept_id": row["concept_id"],
        "concept_name": row["concept_name"] if "concept_name" in row.keys() else None,
        "definition": row["definition"],
        "tension": row["tension"],
        "source": row["source"],
        "source_ref_id": row["source_ref_id"],
        "confidence": row["confidence"],
        "mind_time": row["mind_time"],
        "created_at": row["created_at"],
    }


def _build_working_definitions_context(names: list[str], limit_per_concept: int = 2) -> str:
    rows = db.get_latest_working_definitions_for_names(names, limit_per_concept)
    if not rows:
        return ""
    parts = []
    for row in rows:
        tension = f" Напряжение: {row['tension']}." if row["tension"] else ""
        parts.append(
            f"- «{row['concept_name']}»: {row['definition']}{tension} "
            f"(уверенность {float(row['confidence']):.2f}, {row['mind_time']})"
        )
    return "\n".join(parts)


def _combine_contexts(*contexts: str) -> str:
    return "\n\n".join(c for c in contexts if c.strip())


def _canonical_concept_names(names: list[str]) -> list[str]:
    canonical: list[str] = []
    missing: list[str] = []
    for raw_name in names:
        name = raw_name.strip()
        if not name:
            continue
        concept = db.get_concept_by_name(name) or db.get_concept_by_name_normalized(name)
        if concept:
            if concept["name"] not in canonical:
                canonical.append(concept["name"])
        else:
            missing.append(name)
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Концепции не найдены: {', '.join(missing)}",
        )
    return canonical


def _json_column(row, column: str, fallback):
    try:
        return json.loads(row[column] or json.dumps(fallback))
    except (json.JSONDecodeError, TypeError):
        return fallback


@app.post("/concept/check")
async def check_concept(body: AddConceptBody, _=Depends(auth.require_auth)):
    """Stream concept pre-check: is this already covered? Auth required."""
    if not body.name.strip() or not body.definition.strip():
        raise HTTPException(status_code=422, detail="Имя и определение не могут быть пустыми")

    state = db.get_mind_state()
    td = get_time_display(state["born_at"])
    existing_names = graph.all_names()
    grounding_context = _build_grounding_context(
        _concept_names_in_text(f"{body.name} {body.definition}")
    )
    working_context = _build_working_definitions_context(
        _concept_names_in_text(f"{body.name} {body.definition}")
    )

    async def generate():
        async for chunk in mind_engine.check_concept_stream(
            body.name, body.definition, existing_names, td.mind_age_human,
            connection_count=graph.edge_count(),
            grounding_context=_combine_contexts(working_context, grounding_context),
        ):
            yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/concept/add")
async def add_concept(body: AddConceptBody, _=Depends(auth.require_auth)):
    """Stream concept analysis as SSE. Auth required."""
    if not body.name.strip() or not body.definition.strip():
        raise HTTPException(status_code=422, detail="Имя и определение не могут быть пустыми")
    if db.concept_exists(body.name.strip()):
        raise HTTPException(status_code=409, detail="Концепция уже существует")

    state = db.get_mind_state()
    born_at = state["born_at"]
    td = get_time_display(born_at)
    existing_names = graph.all_names()
    n_edges = graph.edge_count()
    grounding_context = _build_grounding_context(
        _concept_names_in_text(f"{body.name} {body.definition}")
    )
    working_context = _build_working_definitions_context(
        _concept_names_in_text(f"{body.name} {body.definition}")
    )

    async def generate():
        full_text = ""
        async for chunk in mind_engine.analyze_concept_stream(
            body.name, body.definition, existing_names, td.mind_age_human,
            connection_count=n_edges,
            grounding_context=_combine_contexts(working_context, grounding_context),
        ):
            full_text += chunk
            yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

        # Persist the operator-provided concept. Model-suggested relations remain
        # proposals until a later independent cognitive cycle accepts them.
        cid = graph.add_concept(body.name.strip(), body.definition.strip(),
                                td.mind_display, time.time())
        graph.add_processing_log(cid, full_text)

        connections, custom_label, neologism = mind_engine.extract_connections_from_response(full_text)
        proposed_relations: list[str] = []
        inquiry_names = [body.name.strip()]
        for conn in connections:
            other = db.get_concept_by_name(conn.get("concept", ""))
            relationship = " ".join(str(conn.get("relationship", "")).split())
            try:
                confidence = max(0.0, min(1.0, float(conn.get("strength", 0.5))))
            except (TypeError, ValueError):
                confidence = 0.5
            if other and other["id"] != cid and relationship:
                db.record_relation_evidence(
                    cid,
                    other["id"],
                    relationship,
                    "proposed",
                    confidence,
                    time.time(),
                    reason="Предложено первичным анализом новой концепции",
                )
                inquiry_names.append(other["name"])
                proposed_relations.append(
                    f"{body.name.strip()} → {other['name']}: {relationship}"
                )
        if proposed_relations:
            db.create_inquiry(
                f"Какие предложенные связи концепции «{body.name.strip()}» "
                "подтверждаются памятью или внешними основаниями?",
                list(dict.fromkeys(inquiry_names)),
                0.9,
                "operator_concept",
                time.time(),
            )
        label = custom_label or neologism
        if label:
            graph.set_custom_label(cid, label)
        if neologism:
            db.insert_neologism(neologism, full_text[:300], "concept_add", cid,
                                td.mind_display, time.time())

        asyncio.create_task(
            stream_engine.push_reaction(
                f"Оператор добавил концепцию «{body.name.strip()}»: "
                f"{body.definition.strip()}. "
                + (
                    "Связи ожидают проверки: " + "; ".join(proposed_relations[:8])
                    if proposed_relations
                    else "Проверяемые связи пока не предложены."
                ),
                [body.name],
            )
        )

        yield f"data: {json.dumps({'done': True, 'concept_id': cid, 'graph': graph.to_json(since=time.time() - 24 * 3600)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/concept/graph")
def get_graph(hours: int = Query(24, ge=1, le=24 * 30)):
    since = time.time() - hours * 3600
    return graph.to_json(since=since)


@app.get("/concept/list")
def concept_list():
    result = []
    for c in db.list_concepts():
        logs = [{"content": r["content"], "created_at": r["created_at"]}
                for r in db.get_processing_logs(c["id"])]
        conns = db.get_connections_for(c["id"])
        result.append({
            "id": c["id"],
            "name": c["name"],
            "definition": c["definition"],
            "mind_time_added": c["mind_time_added"],
            "real_time_added": c["real_time_added"],
            "is_seed": bool(c["is_seed"]),
            "is_autonomous": bool(c["is_autonomous"]) if "is_autonomous" in c.keys() else False,
            "custom_label": c["custom_label"],
            "connection_count": len(conns),
            "groundings": [
                _grounding_row_to_dict(r)
                for r in db.get_groundings_for_concept(c["id"])
            ],
            "working_definitions": [
                _working_definition_row_to_dict(r)
                for r in db.get_working_definitions_for_concept(c["id"])
            ],
            "connections": [
                {"other_name": r["other_name"],
                 "relationship": r["relationship"],
                 "strength": r["strength"],
                 "confidence": r["confidence"]}
                for r in conns
            ],
            "processing_logs": logs,
        })
    return result


@app.get("/concept/{concept_id}")
def get_concept(concept_id: int):
    data = graph.get_node_data(concept_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Концепция не найдена")
    return data


# ── Grounding excerpts — protected writes, public reads ───────────────────

@app.post("/grounding/excerpt")
async def add_grounding_excerpt(body: GroundingExcerptBody, _=Depends(auth.require_auth)):
    title = body.title.strip()
    excerpt = body.excerpt.strip()
    concept_names = [n.strip() for n in body.concept_names if n.strip()]
    if not title or not excerpt:
        raise HTTPException(
            status_code=422,
            detail="Нужны название и фрагмент",
        )
    if len(excerpt) > MAX_GROUNDING_EXCERPT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Фрагмент не должен превышать {MAX_GROUNDING_EXCERPT_CHARS} символов",
        )

    concepts = []
    missing = []
    for name in concept_names:
        concept = db.get_concept_by_name(name) or db.get_concept_by_name_normalized(name)
        if concept:
            concepts.append(concept)
        else:
            missing.append(name)
    if missing:
        suggestions: list[str] = []
        for name in missing:
            suggestions.extend(r["name"] for r in db.find_concepts_by_name_fragment(name))
        suffix = f". Похожие: {', '.join(dict.fromkeys(suggestions))}" if suggestions else ""
        raise HTTPException(
            status_code=404,
            detail=f"Концепции не найдены: {', '.join(missing)}{suffix}",
        )

    state = db.get_mind_state()
    td = get_time_display(state["born_at"])
    now = time.time()

    analysis = await mind_engine.analyze_grounding_excerpt(
        title,
        excerpt,
        graph.all_names(),
        td.mind_age_human,
        connection_count=graph.edge_count(),
        author=body.author.strip() if body.author else None,
        source=body.source.strip() if body.source else None,
        preferred_concept_names=[c["name"] for c in concepts],
    )

    concepts_by_name = {c["name"].casefold(): c for c in concepts}
    for link in analysis.get("concept_links", []):
        concept = db.get_concept_by_name_normalized(str(link.get("concept", "")))
        if concept:
            concepts_by_name[concept["name"].casefold()] = concept

    if not concepts_by_name:
        for name in _concept_names_in_text(excerpt, limit=8):
            concept = db.get_concept_by_name(name)
            if concept:
                concepts_by_name[concept["name"].casefold()] = concept

    concepts = list(concepts_by_name.values())
    gid = db.insert_grounding_excerpt(
        title,
        body.author.strip() if body.author else None,
        body.source.strip() if body.source else None,
        excerpt,
        td.mind_display,
        now,
    )

    notes_by_name: dict[str, str] = {}
    for link in analysis.get("concept_links", []):
        name = str(link.get("concept", "")).casefold()
        note = str(link.get("note", "")).strip()
        if name and note:
            notes_by_name[name] = note[:500]

    for concept in concepts:
        note = body.note or notes_by_name.get(concept["name"].casefold())
        db.link_grounding_to_concept(concept["id"], gid, note, now)

    linked_names = [c["name"] for c in concepts]
    for item in analysis.get("definitions", []):
        concept = db.get_concept_by_name_normalized(str(item.get("concept", "")))
        definition = str(item.get("definition", "")).strip()
        if not concept or concept["name"] not in linked_names or not definition:
            continue
        tension = item.get("tension")
        if tension is not None:
            tension = str(tension).strip() or None
        try:
            confidence = float(item.get("confidence", 0.55))
        except (TypeError, ValueError):
            confidence = 0.55
        db.insert_working_definition(
            concept["id"], definition[:2000], tension, "grounding",
            gid, confidence, td.mind_display, time.time()
        )

    experience = str(analysis.get("experience") or "").strip()
    if experience:
        asyncio.create_task(
            stream_engine.push_reaction(
                f"Фрагмент превращён в опыт: {experience[:260]}",
                linked_names,
            )
        )

    return {
        "id": gid,
        "title": title,
        "concept_names": linked_names,
        "experience": experience,
        "graph": graph.to_json(since=time.time() - 24 * 3600),
    }


@app.get("/grounding/excerpts")
def grounding_excerpts(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return [_grounding_row_to_dict(r) for r in db.list_groundings(limit, offset)]


# ── Contemplation — protected ──────────────────────────────────────────────

class ContemplateBody(BaseModel):
    thought: str


@app.post("/contemplate")
async def contemplate(body: ContemplateBody, _=Depends(auth.require_auth)):
    if not body.thought.strip():
        raise HTTPException(status_code=422, detail="Мысль не может быть пустой")

    state = db.get_mind_state()
    td = get_time_display(state["born_at"])
    existing_names = graph.all_names()
    involved_names = _concept_names_in_text(body.thought)
    grounding_context = _build_grounding_context(involved_names)
    working_context = _build_working_definitions_context(involved_names)

    async def generate():
        full_text = ""
        visible_text = ""
        pending = ""
        suppress_json = False
        async for chunk in mind_engine.contemplate_stream(
            body.thought, existing_names, td.mind_age_human,
            connection_count=graph.edge_count(),
            grounding_context=_combine_contexts(working_context, grounding_context),
        ):
            full_text += chunk
            if suppress_json:
                continue
            pending += chunk
            marker = re.search(r"```json|```\s*\{", pending, flags=re.IGNORECASE)
            if marker:
                visible_chunk = pending[:marker.start()]
                if visible_chunk:
                    visible_text += visible_chunk
                    yield f"data: {json.dumps({'chunk': visible_chunk}, ensure_ascii=False)}\n\n"
                pending = ""
                suppress_json = True
                continue
            if len(pending) > 16:
                visible_chunk = pending[:-16]
                pending = pending[-16:]
                visible_text += visible_chunk
                yield f"data: {json.dumps({'chunk': visible_chunk}, ensure_ascii=False)}\n\n"

        if pending and not suppress_json:
            visible_text += pending
            yield f"data: {json.dumps({'chunk': pending}, ensure_ascii=False)}\n\n"

        visible_text = visible_text.strip()
        contemplation_id = db.insert_contemplation(
            body.thought, visible_text or full_text, td.mind_display, time.time()
        )
        _, _, neologism = mind_engine.extract_connections_from_response(full_text)
        if neologism:
            db.insert_neologism(neologism, full_text[:300], "contemplation", None,
                                td.mind_display, time.time())
        definitions = await mind_engine.synthesize_working_definitions(
            body.thought,
            visible_text or full_text,
            involved_names,
            td.mind_age_human,
            connection_count=graph.edge_count(),
            grounding_context=grounding_context,
            working_definitions_context=working_context,
        )
        for item in definitions:
            concept = db.get_concept_by_name_normalized(str(item.get("concept", "")))
            definition = str(item.get("definition", "")).strip()
            if not concept or not definition:
                continue
            tension = item.get("tension")
            if tension is not None:
                tension = str(tension).strip() or None
            try:
                confidence = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            db.insert_working_definition(
                concept["id"], definition[:2000], tension, "contemplation",
                contemplation_id, confidence, td.mind_display, time.time()
            )
        asyncio.create_task(stream_engine.push_contemplation((visible_text or full_text)[:300]))
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Stream SSE — PUBLIC ───────────────────────────────────────────────────

@app.get("/stream")
async def stream_sse():
    """Live thought feed via SSE. Public — no auth required."""
    queue = stream_engine.subscribe()

    async def event_generator():
        recent = db.get_stream_events(limit=20)
        for row in reversed(recent):
            payload = {
                "id": row["id"], "mind_time": row["mind_time"],
                "type": row["type"], "content": row["content"],
                "concepts_involved": json.loads(row["concepts_involved"]),
                "created_at": row["created_at"],
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            stream_engine.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )


# ── Mind state — PUBLIC ────────────────────────────────────────────────────

@app.get("/mind/state")
def mind_state():
    state = db.get_mind_state()
    td = get_time_display(state["born_at"])
    # Get total count via a quick DB query
    with db.get_conn() as conn:
        stream_count = conn.execute("SELECT COUNT(*) FROM thought_stream").fetchone()[0]
    return {
        "name": state["name"],
        "born_at": state["born_at"],
        "time": {
            "mind_display": td.mind_display,
            "mind_age_human": td.mind_age_human,
            "real_display": td.real_display,
        },
        "concept_count": graph.node_count(),
        "connection_count": graph.edge_count(),
        "stream_event_count": stream_count,
        "milestones_reached": len(db.list_milestones()),
        "cognitive": db.get_cognitive_metrics(),
    }


# ── Cognitive observability — public reads, protected feedback ─────────────

@app.get("/mind/metrics")
def cognitive_metrics():
    return db.get_cognitive_metrics()


@app.get("/mind/inquiries")
def cognitive_inquiries(
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    allowed = {None, "open", "resolved", "blocked"}
    if status not in allowed:
        raise HTTPException(status_code=422, detail="Недопустимый статус вопроса")
    return [
        {
            **dict(row),
            "concept_names": _json_column(row, "concept_names", []),
        }
        for row in db.list_inquiries(status, limit, offset)
    ]


@app.get("/mind/beliefs")
def cognitive_beliefs(
    status: str = Query("active"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if status not in {"active", "revised", "retracted"}:
        raise HTTPException(status_code=422, detail="Недопустимый статус убеждения")
    return [
        {
            **dict(row),
            "concept_names": _json_column(row, "concept_names", []),
            "evidence_event_ids": _json_column(row, "evidence_event_ids", []),
            "counterevidence_event_ids": _json_column(
                row,
                "counterevidence_event_ids",
                [],
            ),
        }
        for row in db.list_beliefs(status, limit, offset)
    ]


@app.get("/mind/predictions")
def cognitive_predictions(
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if status not in {None, "pending", "resolved"}:
        raise HTTPException(status_code=422, detail="Недопустимый статус прогноза")
    return [
        {
            **dict(row),
            "concept_names": _json_column(row, "concept_names", []),
        }
        for row in db.list_predictions(status, limit, offset)
    ]


@app.get("/mind/cycles")
def cognitive_cycles(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return [
        {
            **dict(row),
            "candidate": _json_column(row, "candidate_json", {}),
            "critique": _json_column(row, "critique_json", {}),
            "memory_event_ids": _json_column(row, "memory_event_ids", []),
        }
        for row in db.list_cognitive_cycles(limit, offset)
    ]


@app.get("/mind/observations")
def cognitive_observations(limit: int = Query(50, ge=1, le=500)):
    return [
        {
            **dict(row),
            "concept_names": _json_column(row, "concept_names", []),
        }
        for row in db.list_external_observations(limit)
    ]


@app.get("/mind/self-model")
def cognitive_self_model():
    return [dict(row) for row in db.list_self_model_entries()]


@app.get("/mind/consolidations")
def cognitive_consolidations(limit: int = Query(20, ge=1, le=100)):
    return [
        {
            **dict(row),
            "source_event_ids": _json_column(row, "source_event_ids", []),
            "result": _json_column(row, "result_json", {}),
        }
        for row in db.list_consolidation_runs(limit)
    ]


@app.post("/mind/observations")
async def add_cognitive_observation(
    body: ExternalObservationBody,
    _=Depends(auth.require_auth),
):
    content = " ".join(body.content.split()).strip()
    source = " ".join(body.source.split()).strip()
    if not content or not source:
        raise HTTPException(status_code=422, detail="Нужны наблюдение и источник")
    if len(content) > 10_000 or len(source) > 500:
        raise HTTPException(status_code=422, detail="Наблюдение или источник слишком длинные")
    if not 0.0 <= body.reliability <= 1.0:
        raise HTTPException(status_code=422, detail="Надёжность должна быть от 0 до 1")
    concept_names = _canonical_concept_names(body.concept_names)
    now = time.time()
    observation_id = db.insert_external_observation(
        content,
        source,
        concept_names,
        body.reliability,
        now,
    )
    event_id = await stream_engine.push_external_event(
        "observation",
        f"Внешнее наблюдение ({source}): {content}",
        concept_names,
        salience=0.9,
        reliability=body.reliability,
    )
    return {"id": observation_id, "event_id": event_id}


@app.post("/mind/predictions/{prediction_id}/resolve")
async def resolve_cognitive_prediction(
    prediction_id: int,
    body: PredictionResolutionBody,
    _=Depends(auth.require_auth),
):
    outcome = body.outcome.strip().casefold()
    evidence = " ".join(body.evidence.split()).strip()
    if outcome not in {"confirmed", "disconfirmed", "inconclusive"}:
        raise HTTPException(status_code=422, detail="Недопустимый исход прогноза")
    if not evidence:
        raise HTTPException(status_code=422, detail="Нужно свидетельство исхода")
    prediction = db.get_prediction(prediction_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail="Прогноз не найден")
    now = time.time()
    if not db.resolve_prediction(prediction_id, outcome, evidence, now):
        raise HTTPException(status_code=409, detail="Прогноз уже закрыт")
    concept_names = _json_column(prediction, "concept_names", [])
    await stream_engine.push_external_event(
        "feedback",
        f"Прогноз #{prediction_id}: {outcome}. Свидетельство: {evidence}",
        concept_names,
        salience=1.0,
        reliability=0.95,
    )
    if outcome == "disconfirmed":
        db.create_inquiry(
            f"Почему был опровергнут прогноз: {prediction['statement']}?",
            concept_names,
            0.95,
            "prediction_disconfirmed",
            now,
        )
    return {"id": prediction_id, "status": "resolved", "outcome": outcome}


# ── History — PUBLIC ───────────────────────────────────────────────────────

@app.get("/history/stream")
def history_stream(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    rows = db.get_stream_events(limit=limit, offset=offset)
    return [
        {
            "id": r["id"],
            "mind_time": r["mind_time"],
            "type": r["type"],
            "content": r["content"],
            "concepts_involved": json.loads(r["concepts_involved"]),
            "created_at": r["created_at"],
            "salience": r["salience"],
            "reliability": r["reliability"],
            "cycle_id": r["cycle_id"],
        }
        for r in rows
    ]


@app.get("/neologisms")
def get_neologisms(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return [dict(r) for r in db.list_neologisms(limit, offset)]


@app.get("/history/contemplations")
def history_contemplations(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return [dict(r) for r in db.get_contemplations(limit=limit, offset=offset)]
