"""
SQLite persistence layer.
All tables are created once on first launch; never drop or alter in production.
"""
import sqlite3
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "mind.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            -- Singleton row: mind birth time and identity
            CREATE TABLE IF NOT EXISTS mind_state (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                born_at    REAL    NOT NULL,
                name       TEXT    NOT NULL DEFAULT 'IMPLUS',
                updated_at REAL    NOT NULL
            );

            -- Every concept the mind has learned
            CREATE TABLE IF NOT EXISTS concepts (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    NOT NULL UNIQUE,
                definition       TEXT    NOT NULL,
                mind_time_added  TEXT    NOT NULL,
                real_time_added  REAL    NOT NULL,
                custom_label     TEXT,
                is_seed          INTEGER NOT NULL DEFAULT 0,
                is_autonomous    INTEGER NOT NULL DEFAULT 0
            );

            -- Graph edges between concepts
            CREATE TABLE IF NOT EXISTS concept_connections (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_a_id INTEGER NOT NULL REFERENCES concepts(id),
                concept_b_id INTEGER NOT NULL REFERENCES concepts(id),
                relationship TEXT,
                strength     REAL    NOT NULL DEFAULT 1.0,
                created_at   REAL    NOT NULL
            );

            -- Claude's step-by-step log for each concept addition
            CREATE TABLE IF NOT EXISTS processing_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_id INTEGER NOT NULL REFERENCES concepts(id),
                content    TEXT    NOT NULL,
                created_at REAL    NOT NULL
            );

            -- Every thought event (spontaneous / reaction / milestone / contemplation)
            CREATE TABLE IF NOT EXISTS thought_stream (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                mind_time         TEXT    NOT NULL,
                type              TEXT    NOT NULL,
                content           TEXT    NOT NULL,
                concepts_involved TEXT    NOT NULL DEFAULT '[]',
                created_at        REAL    NOT NULL
            );

            -- User-submitted contemplations + mind's structured response
            CREATE TABLE IF NOT EXISTS contemplations (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_thought   TEXT NOT NULL,
                mind_response  TEXT NOT NULL,
                mind_time      TEXT NOT NULL,
                created_at     REAL NOT NULL
            );

            -- Reached time milestones
            CREATE TABLE IF NOT EXISTS milestones (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                milestone_key    TEXT    NOT NULL UNIQUE,
                reached_at_real  REAL    NOT NULL,
                reached_at_mind  TEXT    NOT NULL,
                reflection       TEXT
            );
        """)
        conn.commit()
    # Safe migration: add is_autonomous column for existing databases
    try:
        with get_conn() as conn:
            conn.execute(
                "ALTER TABLE concepts ADD COLUMN is_autonomous INTEGER NOT NULL DEFAULT 0"
            )
            conn.commit()
    except Exception:
        pass  # Column already exists — ok


# ── Helpers ────────────────────────────────────────────────────────────────

def get_mind_state() -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM mind_state WHERE id = 1").fetchone()


def create_mind_state(born_at: float, name: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO mind_state (id, born_at, name, updated_at) VALUES (1, ?, ?, ?)",
            (born_at, name, born_at),
        )
        conn.commit()


def insert_concept(name: str, definition: str, mind_time: str,
                   real_time: float, is_seed: bool = False,
                   is_autonomous: bool = False) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO concepts
               (name, definition, mind_time_added, real_time_added, is_seed, is_autonomous)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, definition, mind_time, real_time,
             1 if is_seed else 0, 1 if is_autonomous else 0),
        )
        conn.commit()
        return cur.lastrowid


def concept_exists(name: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM concepts WHERE name=?", (name,)).fetchone()
        return row is not None


def get_concept_by_id(cid: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM concepts WHERE id=?", (cid,)).fetchone()


def get_concept_by_name(name: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM concepts WHERE name=?", (name,)).fetchone()


def list_concepts() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM concepts ORDER BY real_time_added ASC"
        ).fetchall()


def insert_connection(a_id: int, b_id: int, relationship: str,
                      strength: float, created_at: float) -> None:
    with get_conn() as conn:
        # Avoid duplicate edges (undirected)
        existing = conn.execute(
            """SELECT id FROM concept_connections
               WHERE (concept_a_id=? AND concept_b_id=?)
                  OR (concept_a_id=? AND concept_b_id=?)""",
            (a_id, b_id, b_id, a_id),
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO concept_connections
                   (concept_a_id, concept_b_id, relationship, strength, created_at)
                   VALUES (?,?,?,?,?)""",
                (a_id, b_id, relationship, strength, created_at),
            )
            conn.commit()


def get_connections_for(concept_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT cc.*, c.name as other_name
               FROM concept_connections cc
               JOIN concepts c ON (
                 CASE WHEN cc.concept_a_id = ? THEN cc.concept_b_id ELSE cc.concept_a_id END = c.id
               )
               WHERE cc.concept_a_id = ? OR cc.concept_b_id = ?""",
            (concept_id, concept_id, concept_id),
        ).fetchall()


def list_connections() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM concept_connections").fetchall()


def insert_processing_log(concept_id: int, content: str, created_at: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO processing_logs (concept_id, content, created_at) VALUES (?,?,?)",
            (concept_id, content, created_at),
        )
        conn.commit()


def get_processing_logs(concept_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM processing_logs WHERE concept_id=? ORDER BY created_at",
            (concept_id,),
        ).fetchall()


def insert_stream_event(mind_time: str, event_type: str, content: str,
                        concepts: list[str], created_at: float) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO thought_stream
               (mind_time, type, content, concepts_involved, created_at)
               VALUES (?,?,?,?,?)""",
            (mind_time, event_type, content, json.dumps(concepts, ensure_ascii=False), created_at),
        )
        conn.commit()
        return cur.lastrowid


def get_stream_events(limit: int = 100, offset: int = 0) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM thought_stream ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def insert_contemplation(user_thought: str, mind_response: str,
                         mind_time: str, created_at: float) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO contemplations
               (user_thought, mind_response, mind_time, created_at)
               VALUES (?,?,?,?)""",
            (user_thought, mind_response, mind_time, created_at),
        )
        conn.commit()
        return cur.lastrowid


def get_contemplations(limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM contemplations ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def milestone_exists(key: str) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id FROM milestones WHERE milestone_key=?", (key,)
        ).fetchone() is not None


def insert_milestone(key: str, real_time: float, mind_time: str,
                     reflection: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO milestones
               (milestone_key, reached_at_real, reached_at_mind, reflection)
               VALUES (?,?,?,?)""",
            (key, real_time, mind_time, reflection),
        )
        conn.commit()


def list_milestones() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM milestones ORDER BY reached_at_real ASC"
        ).fetchall()


def update_concept_label(concept_id: int, label: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE concepts SET custom_label=? WHERE id=?", (label, concept_id)
        )
        conn.commit()


def get_last_autonomous_time() -> float | None:
    """Return real_time_added of the most recently created autonomous concept, or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(real_time_added) as t FROM concepts WHERE is_autonomous=1"
        ).fetchone()
        return float(row["t"]) if row and row["t"] is not None else None
