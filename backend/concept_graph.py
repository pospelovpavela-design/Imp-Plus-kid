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
                db.upsert_connection(
                    a["id"],
                    b["id"],
                    rel,
                    strength,
                    now,
                    source="seed",
                    confidence=1.0,
                )
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
                confidence=row["confidence"],
                evidence_count=row["evidence_count"],
                created_at=row["created_at"],
            )

    # ── Query ─────────────────────────────────────────────────────────────

    def node_count(self) -> int:
        return self.g.number_of_nodes()

    def edge_count(self) -> int:
        return self.g.number_of_edges()

    def all_names(self) -> list[str]:
        return [self.g.nodes[n]["name"] for n in self.g.nodes if "name" in self.g.nodes[n]]

    def relevant_names(self, focus_names: list[str], limit: int = 36) -> list[str]:
        by_name = {
            self.g.nodes[node_id]["name"].casefold(): node_id
            for node_id in self.g.nodes
            if "name" in self.g.nodes[node_id]
        }
        selected: list[str] = []
        seen: set[int] = set()
        for name in focus_names:
            node_id = by_name.get(name.casefold())
            if node_id is None or node_id in seen:
                continue
            seen.add(node_id)
            selected.append(self.g.nodes[node_id]["name"])
            neighbours = sorted(
                self.g.neighbors(node_id),
                key=lambda other: float(
                    self.g.edges[node_id, other].get("confidence", 0.5)
                ),
                reverse=True,
            )
            for neighbour in neighbours:
                if neighbour in seen:
                    continue
                seen.add(neighbour)
                selected.append(self.g.nodes[neighbour]["name"])
                if len(selected) >= limit:
                    return selected
        return selected

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
        d["groundings"] = [
            {
                "id": r["id"],
                "title": r["title"],
                "author": r["author"],
                "source": r["source"],
                "excerpt": r["excerpt"],
                "note": r["note"],
                "mind_time": r["mind_time"],
                "created_at": r["created_at"],
            }
            for r in db.get_groundings_for_concept(concept_id)
        ]
        d["working_definitions"] = [
            {
                "id": r["id"],
                "concept_id": r["concept_id"],
                "concept_name": r["concept_name"],
                "definition": r["definition"],
                "tension": r["tension"],
                "source": r["source"],
                "source_ref_id": r["source_ref_id"],
                "confidence": r["confidence"],
                "mind_time": r["mind_time"],
                "created_at": r["created_at"],
            }
            for r in db.get_working_definitions_for_concept(concept_id)
        ]
        return d

    def to_json(self, since: float | None = None) -> dict[str, Any]:
        visible_node_ids: set[int] | None = None
        visible_edges = list(self.g.edges(data=True))
        if since is not None:
            visible_edges = [
                (a, b, ed) for a, b, ed in visible_edges
                if float(ed.get("created_at") or 0) >= since
            ]
            visible_node_ids = {
                nid for nid, nd in self.g.nodes(data=True)
                if float(nd.get("real_time_added") or 0) >= since
            }
            for a, b, _ in visible_edges:
                visible_node_ids.add(a)
                visible_node_ids.add(b)

        degree_by_id = dict(self.g.degree())
        if since is not None:
            recent_graph = nx.Graph()
            recent_graph.add_nodes_from(visible_node_ids or set())
            recent_graph.add_edges_from((a, b) for a, b, _ in visible_edges)
            degree_by_id = dict(recent_graph.degree())

        nodes = []
        for nid in self.g.nodes:
            if visible_node_ids is not None and nid not in visible_node_ids:
                continue
            nd = self.g.nodes[nid]
            if "name" not in nd:
                continue
            nodes.append({
                "id": nid,
                "name": nd["name"],
                "is_seed": nd.get("is_seed", False),
                "is_autonomous": nd.get("is_autonomous", False),
                "mind_time_added": nd.get("mind_time_added", ""),
                "degree": degree_by_id.get(nid, 0),
                "grounding_count": len(db.get_groundings_for_concept(nid)),
                "custom_label": nd.get("custom_label"),
            })
        links = []
        for a, b, ed in visible_edges:
            links.append({
                "source": a,
                "target": b,
                "relationship": ed.get("relationship", ""),
                "strength": ed.get("strength", 1.0),
                "confidence": ed.get("confidence", 0.5),
                "created_at": ed.get("created_at"),
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

    def add_connection(
        self,
        a_id: int,
        b_id: int,
        relationship: str,
        strength: float,
        *,
        source: str = "analysis",
        confidence: float | None = None,
    ) -> bool:
        now = time.time()
        connection_id = db.upsert_connection(
            a_id,
            b_id,
            relationship,
            strength,
            now,
            source=source,
            confidence=strength if confidence is None else confidence,
        )
        if connection_id is None:
            return False
        row = db.get_connection_between(a_id, b_id)
        self.g.add_edge(
            a_id,
            b_id,
            relationship=row["relationship"] if row else relationship,
            strength=float(row["strength"]) if row else strength,
            confidence=float(row["confidence"]) if row else confidence or strength,
            evidence_count=int(row["evidence_count"]) if row else 1,
            created_at=float(row["created_at"]) if row else now,
        )
        return True

    def sync_connection(self, a_id: int, b_id: int) -> None:
        """Reflect the persisted active/archive state in the in-memory graph."""
        row = db.get_connection_between(a_id, b_id)
        if row is None or row["status"] != "active" or a_id == b_id:
            if self.g.has_edge(a_id, b_id):
                self.g.remove_edge(a_id, b_id)
            return
        self.g.add_edge(
            a_id,
            b_id,
            relationship=row["relationship"],
            strength=float(row["strength"]),
            confidence=float(row["confidence"]),
            evidence_count=int(row["evidence_count"]),
            created_at=float(row["created_at"]),
        )

    def add_processing_log(self, concept_id: int, content: str) -> None:
        db.insert_processing_log(concept_id, content, time.time())

    def set_custom_label(self, concept_id: int, label: str) -> None:
        db.update_concept_label(concept_id, label)
        if concept_id in self.g.nodes:
            self.g.nodes[concept_id]["custom_label"] = label

    def random_two_concepts(self) -> tuple[dict, dict] | None:
        """Pick two random concepts for spontaneous reflection.

        Uses inverse-degree weighting so rarely-connected concepts appear more
        often than hubs. Prefers non-connected pairs (more interesting), with
        up to 15 retries before falling back to any distinct pair.
        """
        nodes = [n for n in self.g.nodes if "name" in self.g.nodes[n]]
        if len(nodes) < 2:
            return None
        import random
        # Weight: concepts with fewer connections are chosen more often
        max_deg = max(self.g.degree(n) for n in nodes)
        weights = [max_deg - self.g.degree(n) + 1 for n in nodes]
        for _ in range(15):
            a, b = random.choices(nodes, weights=weights, k=2)
            if a != b and not self.g.has_edge(a, b):
                return self.g.nodes[a] | {"id": a}, self.g.nodes[b] | {"id": b}
        # Fallback: any two distinct nodes
        a, b = random.sample(nodes, 2)
        return self.g.nodes[a] | {"id": a}, self.g.nodes[b] | {"id": b}
