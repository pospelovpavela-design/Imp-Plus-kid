"""
Pydantic request/response models.
Centralised here so main.py stays clean.
"""
from pydantic import BaseModel, Field
from typing import Optional


# ── Auth ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


# ── Concept ───────────────────────────────────────────────────────────────

class AddConceptRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    definition: str = Field(..., min_length=1, max_length=2000)


class ConceptConnectionOut(BaseModel):
    other_name: str
    relationship: str
    strength: float


class ConceptOut(BaseModel):
    id: int
    name: str
    definition: str
    mind_time_added: str
    real_time_added: float
    is_seed: bool
    custom_label: Optional[str]
    connection_count: int
    connections: list[ConceptConnectionOut]
    processing_logs: list[dict]


# ── Contemplation ─────────────────────────────────────────────────────────

class ContemplateRequest(BaseModel):
    thought: str = Field(..., min_length=1, max_length=4000)


class ContemplationHistoryItem(BaseModel):
    id: int
    user_thought: str
    mind_response: str
    mind_time: str
    created_at: float


# ── Time ──────────────────────────────────────────────────────────────────

class TimeResponse(BaseModel):
    mind_display: str
    mind_age_human: str
    mind_total_seconds: float
    mind_days: int
    mind_hours: int
    mind_minutes: int
    mind_seconds: int
    real_display: str
    real_total_seconds: float
    ratio: int
    born_at: float


# ── Graph ─────────────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: int
    name: str
    is_seed: bool
    mind_time_added: str
    degree: int
    custom_label: Optional[str]


class GraphLink(BaseModel):
    source: int
    target: int
    relationship: str
    strength: float


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]


# ── Stream ────────────────────────────────────────────────────────────────

class ThoughtEvent(BaseModel):
    id: int
    mind_time: str
    type: str
    content: str
    concepts_involved: list[str]
    created_at: float


# ── Mind State ────────────────────────────────────────────────────────────

class MindStateResponse(BaseModel):
    name: str
    born_at: float
    time: dict
    concept_count: int
    connection_count: int
    stream_event_count: int
    milestones_reached: int
