#!/usr/bin/env python3
"""Read-only cognitive invariants and experiment metrics for an IMPLUS database."""

import argparse
import json
import sqlite3
from pathlib import Path


def scalar(conn: sqlite3.Connection, query: str, params=()):
    return conn.execute(query, params).fetchone()[0]


def audit(database: Path) -> dict:
    uri = f"file:{database.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        concepts = scalar(conn, "SELECT COUNT(*) FROM concepts")
        active_edges = scalar(
            conn,
            """SELECT COUNT(*) FROM concept_connections
               WHERE status='active' AND concept_a_id<>concept_b_id""",
        )
        archived_edges = scalar(
            conn,
            "SELECT COUNT(*) FROM concept_connections WHERE status='archived'",
        )
        self_loops = scalar(
            conn,
            """SELECT COUNT(*) FROM concept_connections
               WHERE status='active' AND concept_a_id=concept_b_id""",
        )
        fallback_edges = scalar(
            conn,
            """SELECT COUNT(*) FROM concept_connections
               WHERE status='active' AND relationship='спонтанная связь'""",
        )
        grounded = scalar(
            conn,
            "SELECT COUNT(DISTINCT concept_id) FROM concept_groundings",
        )
        cycles = scalar(conn, "SELECT COUNT(*) FROM cognitive_cycles")
        accepted = scalar(
            conn,
            """SELECT COUNT(*) FROM cognitive_cycles
               WHERE verdict IN ('accept', 'revise')""",
        )
        predictions = conn.execute(
            """SELECT outcome, confidence FROM predictions
               WHERE status='resolved'
                 AND outcome IN ('confirmed', 'disconfirmed')"""
        ).fetchall()
        daily_insights = scalar(conn, "SELECT COUNT(*) FROM daily_insights")
        unsent_daily_insights = scalar(
            conn,
            "SELECT COUNT(*) FROM daily_insights WHERE sent_at IS NULL",
        )

    max_edges = concepts * (concepts - 1) / 2 if concepts > 1 else 0
    brier = None
    if predictions:
        brier = sum(
            (float(confidence) - (1.0 if outcome == "confirmed" else 0.0)) ** 2
            for outcome, confidence in predictions
        ) / len(predictions)
    return {
        "database": str(database),
        "invariants_ok": self_loops == 0 and fallback_edges == 0,
        "active_self_loops": self_loops,
        "active_fallback_edges": fallback_edges,
        "concepts": concepts,
        "active_edges": active_edges,
        "archived_edges": archived_edges,
        "active_graph_density": active_edges / max_edges if max_edges else 0.0,
        "grounding_coverage": grounded / concepts if concepts else 0.0,
        "cognitive_cycles": cycles,
        "accepted_cycle_rate": accepted / cycles if cycles else None,
        "resolved_predictions": len(predictions),
        "prediction_brier_score": brier,
        "daily_insights": daily_insights,
        "unsent_daily_insights": unsent_daily_insights,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "mind.db",
    )
    args = parser.parse_args()
    result = audit(args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["invariants_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
