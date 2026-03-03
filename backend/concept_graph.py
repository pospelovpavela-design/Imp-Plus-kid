"""
In-memory concept graph backed by networkx.
Loaded from SQLite on startup; every mutation is persisted immediately.
"""
import time
import json
import networkx as nx
from typing import Any

import db
from time_engine import format_mind_timestamp

# Seed concepts present at mind birth
SEED_CONCEPTS: list[tuple[str, str]] = [
    ("есть/нет",           "Фундаментальное различие между существованием и отсутствием"),
    ("я/не-я",             "Различие между собой и всем остальным"),
    ("до/после",           "Порядок событий во времени"),
    ("одинаково/различно", "Отношение сходства и различия между объектами"),
    ("больше/меньше",      "Отношение величин"),
    ("здесь/не-здесь",     "Различие положения в пространстве"),
]


class ConceptGraph:
    def __init__(self, born_at: float):
        self.born_at = born_at
        self.g = nx.Graph()
        self._load_from_db()

    # ── Bootstrap ─────────────────────────────────────────────────────────

    def bootstrap_seeds(self) -> None:
        """Call once on first launch to plant seed concepts."""
        now = time.time()
        mind_time = format_mind_timestamp(self.born_at, now)
        for name, definition in SEED_CONCEPTS:
            if not db.concept_exists(name):
                cid = db.insert_concept(name, definition, mind_time, now, is_seed=True)
                self.g.add_node(cid, name=name, definition=definition,
                                mind_time_added=mind_time, real_time_added=now,
                                is_seed=True, custom_label=None)
        # Connect seed pairs that are logically adjacent
        seed_pairs = [
            ("есть/нет", "я/не-я",    "базовое разделение",   0.9),
            ("есть/нет", "до/после",  "существование во времени", 0.7),
            ("я/не-я",   "здесь/не-здесь", "пространственная граница", 0.8),
            ("до/после", "больше/меньше",  "упорядочение",     0.6),
            ("одинаково/различно", "больше/меньше", "сравнение", 0.8),
        ]
        for a_name, b_name, rel, strength in seed_pairs:
            a = db.get_concept_by_name(a_name)
            b = db.get_concept_by_name(b_name)
            if a and b:
                db.insert_connection(a["id"], b["id"], rel, strength, now)
                self.g.add_edge(a["id"], b["id"], relationship=rel, strength=strength)

    # ── Load ──────────────────────────────────────────────────────────────

    def _load_from_db(self) -> None:
        for row in db.list_concepts():
            keys = row.keys()
            self.g.add_node(
                row["id"],
                name=row["name"],
                definition=row["definition"],
                mind_time_added=row["mind_time_added"],
                real_time_added=row["real_time_added"],
                is_seed=bool(row["is_seed"]),
                is_autonomous=bool(row["is_autonomous"]) if "is_autonomous" in keys else False,
                custom_label=row["custom_label"],
            )
        for row in db.list_connections():
            self.g.add_edge(
                row["concept_a_id"], row["concept_b_id"],
                relationship=row["relationship"],
                strength=row["strength"],
            )

    # ── Query ─────────────────────────────────────────────────────────────

    def node_count(self) -> int:
        return self.g.number_of_nodes()

    def edge_count(self) -> int:
        return self.g.number_of_edges()

    def all_names(self) -> list[str]:
        return [self.g.nodes[n]["name"] for n in self.g.nodes]

    def get_node_data(self, concept_id: int) -> dict | None:
        if concept_id not in self.g.nodes:
            return None
        d = dict(self.g.nodes[concept_id])
        d["id"] = concept_id
        d["degree"] = self.g.degree(concept_id)
        neighbours = []
        for nb in self.g.neighbors(concept_id):
            edge = self.g.edges[concept_id, nb]
            neighbours.append({
                "id": nb,
                "name": self.g.nodes[nb]["name"],
                "relationship": edge.get("relationship", ""),
                "strength": edge.get("strength", 1.0),
            })
        d["neighbours"] = neighbours
        d["processing_logs"] = [
            {"content": r["content"], "created_at": r["created_at"]}
            for r in db.get_processing_logs(concept_id)
        ]
        return d

    def to_json(self) -> dict[str, Any]:
        nodes = []
        for nid in self.g.nodes:
            nd = self.g.nodes[nid]
            nodes.append({
                "id": nid,
                "name": nd["name"],
                "is_seed": nd.get("is_seed", False),
                "is_autonomous": nd.get("is_autonomous", False),
                "mind_time_added": nd.get("mind_time_added", ""),
                "degree": self.g.degree(nid),
                "custom_label": nd.get("custom_label"),
            })
        links = []
        for a, b, ed in self.g.edges(data=True):
            links.append({
                "source": a,
                "target": b,
                "relationship": ed.get("relationship", ""),
                "strength": ed.get("strength", 1.0),
            })
        return {"nodes": nodes, "links": links}

    # ── Mutate ────────────────────────────────────────────────────────────

    def add_concept(self, name: str, definition: str,
                    mind_time: str, real_time: float,
                    is_autonomous: bool = False) -> int:
        """Insert concept into graph and DB. Returns new concept_id."""
        cid = db.insert_concept(name, definition, mind_time, real_time,
                                is_autonomous=is_autonomous)
        self.g.add_node(
            cid, name=name, definition=definition,
            mind_time_added=mind_time, real_time_added=real_time,
            is_seed=False, is_autonomous=is_autonomous, custom_label=None,
        )
        return cid

    def add_connection(self, a_id: int, b_id: int,
                       relationship: str, strength: float) -> None:
        now = time.time()
        db.insert_connection(a_id, b_id, relationship, strength, now)
        if not self.g.has_edge(a_id, b_id):
            self.g.add_edge(a_id, b_id, relationship=relationship, strength=strength)

    def add_processing_log(self, concept_id: int, content: str) -> None:
        db.insert_processing_log(concept_id, content, time.time())

    def set_custom_label(self, concept_id: int, label: str) -> None:
        db.update_concept_label(concept_id, label)
        if concept_id in self.g.nodes:
            self.g.nodes[concept_id]["custom_label"] = label

    def random_two_concepts(self) -> tuple[dict, dict] | None:
        """Pick two random connected (or any) concepts for spontaneous reflection."""
        nodes = list(self.g.nodes)
        if len(nodes) < 2:
            return None
        import random
        # Prefer pairs that are NOT directly connected (more interesting)
        non_connected = [(a, b) for a, b in
                         nx.non_edges(self.g) if a in self.g and b in self.g]
        if non_connected:
            a, b = random.choice(non_connected[:50])  # cap for perf
        else:
            a, b = random.sample(nodes, 2)
        return self.g.nodes[a] | {"id": a}, self.g.nodes[b] | {"id": b}
