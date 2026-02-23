"""
FastAPI application — entry point.
Run with: uvicorn backend.main:app --reload --port 8000
"""
import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from pathlib import Path
from dotenv import load_dotenv
# Load .env from project root regardless of working directory
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import db
import stream_engine
import mind_engine
import auth
from concept_graph import ConceptGraph
from time_engine import get_time_display, format_mind_timestamp

# ── App state ──────────────────────────────────────────────────────────────

graph: ConceptGraph | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    db.init_db()

    # Bootstrap mind if first launch
    state = db.get_mind_state()
    born_at: float
    mind_name = os.environ.get("MIND_NAME", "IMPLUS")

    if state is None:
        born_at = time.time()
        db.create_mind_state(born_at, mind_name)
        print(f"[IMPLUS] First launch — mind born at {born_at}")
        graph = ConceptGraph(born_at)
        graph.bootstrap_seeds()
    else:
        born_at = state["born_at"]
        print(f"[IMPLUS] Resuming mind born at {born_at}")
        graph = ConceptGraph(born_at)

    stream_engine.init(born_at, graph)

    # Start background spontaneous-thought loop
    task = asyncio.create_task(stream_engine.spontaneous_loop())
    yield
    task.cancel()


app = FastAPI(title="IMPLUS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ───────────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    password: str


@app.post("/auth/login")
def login(body: LoginBody):
    if not auth.verify_password(body.password):
        raise HTTPException(status_code=401, detail="Неверный пароль")
    return {"token": auth.create_token()}


# ── Time ───────────────────────────────────────────────────────────────────

@app.get("/time")
def get_time(_=Depends(auth.require_auth)):
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
def get_milestones(_=Depends(auth.require_auth)):
    return [dict(r) for r in db.list_milestones()]


# ── Concept ────────────────────────────────────────────────────────────────

class AddConceptBody(BaseModel):
    name: str
    definition: str


@app.post("/concept/add")
async def add_concept(body: AddConceptBody, _=Depends(auth.require_auth)):
    """Stream concept analysis as SSE."""
    if not body.name.strip() or not body.definition.strip():
        raise HTTPException(status_code=422, detail="Имя и определение не могут быть пустыми")
    if db.concept_exists(body.name.strip()):
        raise HTTPException(status_code=409, detail="Концепция уже существует")

    state = db.get_mind_state()
    born_at = state["born_at"]
    td = get_time_display(born_at)
    mind_time = td.mind_display
    existing_names = graph.all_names()

    accumulated = []

    async def generate():
        nonlocal accumulated
        full_text = ""
        async for chunk in mind_engine.analyze_concept_stream(
            body.name, body.definition, existing_names, td.mind_age_human
        ):
            full_text += chunk
            accumulated.append(chunk)
            yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

        # After streaming: persist concept + connections
        cid = graph.add_concept(body.name.strip(), body.definition.strip(),
                                mind_time, time.time())
        graph.add_processing_log(cid, full_text)

        connections, custom_label = mind_engine.extract_connections_from_response(full_text)
        for conn in connections:
            other = db.get_concept_by_name(conn.get("concept", ""))
            if other:
                graph.add_connection(cid, other["id"],
                                     conn.get("relationship", ""),
                                     float(conn.get("strength", 0.5)))

        if custom_label:
            graph.set_custom_label(cid, custom_label)

        # Broadcast reaction to stream feed
        asyncio.create_task(
            stream_engine.push_reaction(
                f"Добавлена концепция «{body.name}». " + full_text[:200],
                [body.name],
            )
        )

        graph_json = graph.to_json()
        yield f"data: {json.dumps({'done': True, 'concept_id': cid, 'graph': graph_json}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/concept/graph")
def get_graph(_=Depends(auth.require_auth)):
    return graph.to_json()


@app.get("/concept/list")
def concept_list(_=Depends(auth.require_auth)):
    concepts = []
    for c in db.list_concepts():
        logs = [{"content": r["content"], "created_at": r["created_at"]}
                for r in db.get_processing_logs(c["id"])]
        conns = db.get_connections_for(c["id"])
        concepts.append({
            "id": c["id"],
            "name": c["name"],
            "definition": c["definition"],
            "mind_time_added": c["mind_time_added"],
            "real_time_added": c["real_time_added"],
            "is_seed": bool(c["is_seed"]),
            "custom_label": c["custom_label"],
            "connection_count": len(conns),
            "connections": [
                {"other_name": r["other_name"],
                 "relationship": r["relationship"],
                 "strength": r["strength"]}
                for r in conns
            ],
            "processing_logs": logs,
        })
    return concepts


@app.get("/concept/{concept_id}")
def get_concept(concept_id: int, _=Depends(auth.require_auth)):
    data = graph.get_node_data(concept_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Концепция не найдена")
    return data


# ── Contemplation ──────────────────────────────────────────────────────────

class ContemplateBody(BaseModel):
    thought: str


@app.post("/contemplate")
async def contemplate(body: ContemplateBody, _=Depends(auth.require_auth)):
    if not body.thought.strip():
        raise HTTPException(status_code=422, detail="Мысль не может быть пустой")

    state = db.get_mind_state()
    born_at = state["born_at"]
    td = get_time_display(born_at)
    existing_names = graph.all_names()

    async def generate():
        full_text = ""
        async for chunk in mind_engine.contemplate_stream(
            body.thought, existing_names, td.mind_age_human
        ):
            full_text += chunk
            yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

        db.insert_contemplation(body.thought, full_text, td.mind_display, time.time())
        asyncio.create_task(stream_engine.push_contemplation(full_text[:300]))
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ── Stream (SSE) ───────────────────────────────────────────────────────────

@app.get("/stream")
async def stream_sse(
    token: str = Query(...),
    _=Depends(auth.require_auth),
):
    """Server-Sent Events endpoint for live thought feed."""
    queue = stream_engine.subscribe()

    async def event_generator():
        # Send last 20 events on connect
        recent = db.get_stream_events(limit=20)
        for row in reversed(recent):
            payload = {
                "id": row["id"],
                "mind_time": row["mind_time"],
                "type": row["type"],
                "content": row["content"],
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
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Mind state ─────────────────────────────────────────────────────────────

@app.get("/mind/state")
def mind_state(_=Depends(auth.require_auth)):
    state = db.get_mind_state()
    td = get_time_display(state["born_at"])
    contemplation_count = db.count_contemplations() if hasattr(db, "count_contemplations") else 0
    stream_count = len(db.get_stream_events(limit=10000))
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
    }


# ── History ────────────────────────────────────────────────────────────────

@app.get("/history/stream")
def history_stream(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(auth.require_auth),
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
        }
        for r in rows
    ]


@app.get("/history/contemplations")
def history_contemplations(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(auth.require_auth),
):
    rows = db.get_contemplations(limit=limit, offset=offset)
    return [dict(r) for r in rows]
