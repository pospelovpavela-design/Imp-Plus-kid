import asyncio
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
import cognitive_engine
import daily_insight_engine
import digest
from concept_graph import ConceptGraph


class CognitiveStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "mind.db"
        db.init_db()
        now = time.time()
        self.a_id = db.insert_concept("альфа", "первая", "День 1", now)
        self.b_id = db.insert_concept("бета", "вторая", "День 1", now)

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_migration_archives_known_graph_pollution_without_deleting_rows(self):
        now = time.time()
        with db.get_conn() as conn:
            conn.executemany(
                """INSERT INTO concept_connections
                   (concept_a_id, concept_b_id, relationship, strength, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (self.a_id, self.a_id, "самоссылка", 0.4, now),
                    (self.a_id, self.b_id, "спонтанная связь", 0.3, now),
                ],
            )
            conn.commit()

        db.init_db()

        with db.get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM concept_connections"
            ).fetchone()[0]
            archived = conn.execute(
                """SELECT COUNT(*) FROM concept_connections
                   WHERE status='archived'"""
            ).fetchone()[0]
        self.assertEqual(total, 2)
        self.assertEqual(archived, 2)
        self.assertEqual(db.list_connections(), [])

    def test_connection_revision_and_contradiction_archive(self):
        now = time.time()
        connection_id = db.upsert_connection(
            self.a_id,
            self.b_id,
            "различает",
            0.7,
            now,
            source="critic_accepted",
            confidence=0.8,
        )
        db.upsert_connection(
            self.b_id,
            self.a_id,
            "уточняет",
            0.9,
            now + 1,
            source="critic_accepted",
            confidence=0.9,
        )
        relation = db.get_connection_between(self.a_id, self.b_id)
        self.assertEqual(relation["relationship"], "уточняет")
        self.assertEqual(relation["evidence_count"], 2)

        for offset in range(3):
            db.record_relation_evidence(
                self.a_id,
                self.b_id,
                "уточняет",
                "contradict",
                0.8,
                now + 2 + offset,
                connection_id=connection_id,
                reason="контрпример",
            )
        relation = db.get_connection_between(self.a_id, self.b_id)
        self.assertEqual(relation["status"], "archived")
        self.assertEqual(relation["contradiction_count"], 3)

    def test_memory_inquiry_prediction_and_metrics(self):
        now = time.time()
        event_id = db.insert_stream_event(
            "День 1",
            "observation",
            "Альфа наблюдаемо отличается от беты.",
            ["альфа", "бета"],
            now,
            salience=0.9,
            reliability=0.95,
        )
        rows = db.search_memory_events(["Альфа"], limit=10)
        self.assertIn(event_id, {row["id"] for row in rows})

        inquiry_id = db.create_inquiry(
            "Чем альфа отличается от беты?",
            ["альфа", "бета"],
            0.8,
            "test",
            now,
        )
        self.assertEqual(db.get_next_inquiry(now)["id"], inquiry_id)
        db.record_inquiry_attempt(inquiry_id, "ответ", True, now + 1)
        self.assertEqual(db.list_inquiries("resolved")[0]["id"], inquiry_id)

        prediction_id = db.insert_prediction(
            "Альфа сохранит различие.",
            "Повторить наблюдение.",
            ["альфа"],
            0.75,
            now,
        )
        self.assertTrue(
            db.resolve_prediction(
                prediction_id,
                "confirmed",
                "Повторное наблюдение совпало.",
                now + 2,
            )
        )
        metrics = db.get_cognitive_metrics()
        self.assertEqual(metrics["active_self_loops"], 0)
        self.assertEqual(metrics["active_fallback_edges"], 0)
        self.assertEqual(metrics["resolved_predictions"], 1)
        self.assertAlmostEqual(metrics["prediction_brier_score"], 0.0625)

    def test_self_connections_and_empty_labels_are_rejected(self):
        now = time.time()
        self.assertIsNone(
            db.upsert_connection(
                self.a_id,
                self.a_id,
                "самоссылка",
                1.0,
                now,
                source="test",
                confidence=1.0,
            )
        )
        self.assertIsNone(
            db.upsert_connection(
                self.a_id,
                self.b_id,
                " ",
                1.0,
                now,
                source="test",
                confidence=1.0,
            )
        )

    async def _run_mocked_cycle(self, graph, candidate, critique):
        with (
            patch(
                "cognitive_engine.mind_engine.generate_cognitive_candidate",
                new=AsyncMock(return_value=candidate),
            ),
            patch(
                "cognitive_engine.mind_engine.critique_cognitive_candidate",
                new=AsyncMock(return_value=critique),
            ),
        ):
            return await cognitive_engine.run_cycle(graph, time.time() - 60)

    def test_cognitive_cycle_only_applies_critic_accepted_relations(self):
        graph = ConceptGraph(time.time() - 60)
        now = time.time()
        db.create_inquiry(
            "Как связаны альфа и бета?",
            ["альфа", "бета"],
            0.9,
            "test",
            now,
        )
        candidate = {
            "observation": "Предложена проверяемая связь.",
            "evidence_memory_ids": [],
            "relations": [
                {
                    "source": "альфа",
                    "target": "бета",
                    "relationship": "различает",
                    "strength": 0.8,
                    "confidence": 0.8,
                }
            ],
            "uncertainty": "Нужна повторная проверка.",
            "next_question": None,
            "prediction": None,
        }
        accepted = {
            "verdict": "accept",
            "reason": "Связь поддержана.",
            "reliability": 0.8,
            "revised_observation": None,
            "accepted_relations": [
                {
                    "source": "альфа",
                    "target": "бета",
                    "relationship": "различает",
                    "strength": 0.8,
                    "confidence": 0.8,
                    "reason": "Проверено.",
                }
            ],
            "contradictions": [],
            "inquiry_resolved": True,
        }
        event = asyncio.run(self._run_mocked_cycle(graph, candidate, accepted))
        self.assertEqual(event["accepted_relations"], 1)
        self.assertEqual(graph.edge_count(), 1)

        third_id = db.insert_concept("гамма", "третья", "День 1", now)
        graph.g.add_node(
            third_id,
            name="гамма",
            definition="третья",
            mind_time_added="День 1",
            real_time_added=now,
            is_seed=False,
            is_autonomous=False,
            custom_label=None,
        )
        db.create_inquiry(
            "Связаны ли альфа и гамма?",
            ["альфа", "гамма"],
            1.0,
            "test",
            now,
        )
        rejected_candidate = {
            **candidate,
            "relations": [
                {
                    "source": "альфа",
                    "target": "гамма",
                    "relationship": "совпадает",
                    "strength": 0.9,
                    "confidence": 0.9,
                }
            ],
        }
        rejected = {
            **accepted,
            "verdict": "needs_evidence",
            "reliability": 0.4,
            "accepted_relations": [],
            "inquiry_resolved": False,
        }
        event = asyncio.run(
            self._run_mocked_cycle(graph, rejected_candidate, rejected)
        )
        self.assertEqual(event["accepted_relations"], 0)
        self.assertIsNone(db.get_connection_between(self.a_id, third_id))

    def test_daily_insight_is_evidence_bounded_and_idempotent(self):
        now = time.time()
        event_id = db.insert_stream_event(
            "День 1",
            "observation",
            "Альфа сохранила наблюдаемое различие.",
            ["альфа"],
            now,
            salience=0.9,
            reliability=0.9,
        )
        cycle_id = db.insert_cognitive_cycle(
            "test",
            "альфа ↔ бета",
            {
                "observation": "Различие повторилось.",
                "relations": [],
            },
            {
                "verdict": "accept",
                "reliability": 0.8,
                "reason": "Поддержано наблюдением.",
            },
            [event_id],
            "accept",
            0.8,
            now,
        )
        candidate = {
            "continuation": "различие устойчиво.",
            "evidence_event_ids": [event_id, 999999],
            "evidence_cycle_ids": [cycle_id, 999999],
            "confidence": 0.75,
        }
        critique = {
            "continuation": (
                "Сегодня за день я понял, что устойчивым можно считать только "
                "повторённое различие."
            ),
            "evidence_event_ids": [event_id, 999999],
            "evidence_cycle_ids": [cycle_id, 999999],
            "confidence": 0.8,
            "reason": "Есть наблюдение и принятый цикл.",
        }
        with (
            patch(
                "daily_insight_engine.mind_engine.generate_daily_insight_candidate",
                new=AsyncMock(return_value=candidate),
            ),
            patch(
                "daily_insight_engine.mind_engine.critique_daily_insight_candidate",
                new=AsyncMock(return_value=critique),
            ),
        ):
            insight, created = asyncio.run(
                daily_insight_engine.generate_for_date(
                    daily_insight_engine.local_today(now),
                    now - 3600,
                    now=now,
                )
            )
            repeated, repeated_created = asyncio.run(
                daily_insight_engine.generate_for_date(
                    daily_insight_engine.local_today(now),
                    now - 3600,
                    now=now,
                )
            )

        self.assertTrue(created)
        self.assertFalse(repeated_created)
        self.assertEqual(insight["id"], repeated["id"])
        self.assertEqual(
            insight["content"].count(daily_insight_engine.PREFIX),
            1,
        )
        self.assertEqual(insight["source_event_ids"], [event_id])
        self.assertEqual(insight["source_cycle_ids"], [cycle_id])
        with db.get_conn() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM daily_insights").fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM thought_stream WHERE type='daily_insight'"
                ).fetchone()[0],
                1,
            )

    def test_telegram_digest_sends_only_unsent_daily_insight_once(self):
        now = time.time()
        row, created = db.insert_daily_insight(
            daily_insight_engine.local_today(now).isoformat(),
            "Сегодня за день я понял, что проверка важнее повторения.",
            0.8,
            [],
            [],
            {},
            "День 1",
            [],
            now,
        )
        self.assertTrue(created)

        async def prepare():
            current = db.get_daily_insight(row["local_date"])
            return daily_insight_engine.row_to_dict(current)

        with (
            patch("digest.prepare_today", side_effect=prepare),
            patch("digest.send_telegram", return_value=True) as send,
        ):
            self.assertEqual(digest.main(), 0)
            self.assertEqual(digest.main(), 0)

        send.assert_called_once_with(row["content"])
        self.assertIsNotNone(db.get_daily_insight(row["local_date"])["sent_at"])


if __name__ == "__main__":
    unittest.main()
