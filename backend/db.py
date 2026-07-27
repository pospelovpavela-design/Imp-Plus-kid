"""SQLite persistence with additive, non-destructive production migrations."""
import sqlite3
import json
import hashlib
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "mind.db"


def _norm_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _fingerprint(value: str) -> str:
    return hashlib.sha256(_norm_text(value).encode()).hexdigest()


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

            -- LLM step-by-step log for each concept addition
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

            -- Neologisms coined by the mind
            CREATE TABLE IF NOT EXISTS neologisms (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                word        TEXT    NOT NULL,
                explanation TEXT,
                source      TEXT    NOT NULL,
                concept_id  INTEGER,
                mind_time   TEXT    NOT NULL,
                created_at  REAL    NOT NULL
            );

            -- Textual fragments that ground concepts in described experience
            CREATE TABLE IF NOT EXISTS grounding_excerpts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                author      TEXT,
                source      TEXT,
                excerpt     TEXT    NOT NULL,
                mind_time   TEXT    NOT NULL,
                created_at  REAL    NOT NULL
            );

            -- Many-to-many links between concepts and grounding fragments
            CREATE TABLE IF NOT EXISTS concept_groundings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_id   INTEGER NOT NULL REFERENCES concepts(id),
                grounding_id INTEGER NOT NULL REFERENCES grounding_excerpts(id),
                note         TEXT,
                created_at   REAL    NOT NULL,
                UNIQUE(concept_id, grounding_id)
            );

            -- Evolving internal definitions synthesized by the mind
            CREATE TABLE IF NOT EXISTS concept_working_definitions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_id       INTEGER NOT NULL REFERENCES concepts(id),
                definition       TEXT    NOT NULL,
                tension          TEXT,
                source           TEXT    NOT NULL,
                source_ref_id    INTEGER,
                confidence       REAL    NOT NULL DEFAULT 0.5,
                mind_time        TEXT    NOT NULL,
                created_at       REAL    NOT NULL
            );
        """)
        conn.commit()

    # Safe migration: add is_autonomous column for existing databases.
    try:
        with get_conn() as conn:
            conn.execute(
                "ALTER TABLE concepts ADD COLUMN is_autonomous INTEGER NOT NULL DEFAULT 0"
            )
            conn.commit()
    except sqlite3.OperationalError:
        pass

    # Safe migration for databases created before textual grounding existed.
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS grounding_excerpts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                author      TEXT,
                source      TEXT,
                excerpt     TEXT    NOT NULL,
                mind_time   TEXT    NOT NULL,
                created_at  REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS concept_groundings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_id   INTEGER NOT NULL REFERENCES concepts(id),
                grounding_id INTEGER NOT NULL REFERENCES grounding_excerpts(id),
                note         TEXT,
                created_at   REAL    NOT NULL,
                UNIQUE(concept_id, grounding_id)
            );

            CREATE TABLE IF NOT EXISTS concept_working_definitions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_id       INTEGER NOT NULL REFERENCES concepts(id),
                definition       TEXT    NOT NULL,
                tension          TEXT,
                source           TEXT    NOT NULL,
                source_ref_id    INTEGER,
                confidence       REAL    NOT NULL DEFAULT 0.5,
                mind_time        TEXT    NOT NULL,
                created_at       REAL    NOT NULL
            );
        """)
        conn.commit()

    _init_cognitive_schema()


def _ensure_column(conn: sqlite3.Connection, table: str, declaration: str) -> None:
    column = declaration.split()[0]
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {declaration}")


def _init_cognitive_schema() -> None:
    """Add non-destructive cognitive-state migrations and memory indexes."""
    with get_conn() as conn:
        _ensure_column(conn, "concept_connections", "status TEXT NOT NULL DEFAULT 'active'")
        _ensure_column(conn, "concept_connections", "confidence REAL NOT NULL DEFAULT 0.5")
        _ensure_column(conn, "concept_connections", "evidence_count INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "concept_connections", "contradiction_count INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "concept_connections", "source TEXT NOT NULL DEFAULT 'legacy'")
        _ensure_column(conn, "concept_connections", "updated_at REAL")
        _ensure_column(conn, "thought_stream", "salience REAL NOT NULL DEFAULT 0.5")
        _ensure_column(conn, "thought_stream", "reliability REAL NOT NULL DEFAULT 0.5")
        _ensure_column(conn, "thought_stream", "consolidated INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "thought_stream", "cycle_id INTEGER")

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cognitive_cycles (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger          TEXT    NOT NULL,
                focus            TEXT    NOT NULL,
                inquiry_id       INTEGER,
                candidate_json   TEXT    NOT NULL,
                critique_json    TEXT    NOT NULL,
                memory_event_ids TEXT    NOT NULL DEFAULT '[]',
                verdict          TEXT    NOT NULL,
                reliability      REAL    NOT NULL DEFAULT 0.0,
                created_at       REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS relation_evidence (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id  INTEGER,
                concept_a_id   INTEGER NOT NULL REFERENCES concepts(id),
                concept_b_id   INTEGER NOT NULL REFERENCES concepts(id),
                relationship   TEXT    NOT NULL,
                verdict        TEXT    NOT NULL,
                confidence     REAL    NOT NULL,
                source_event_id INTEGER,
                cycle_id       INTEGER,
                reason         TEXT,
                created_at     REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS beliefs (
                id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint              TEXT    NOT NULL UNIQUE,
                statement                TEXT    NOT NULL,
                concept_names            TEXT    NOT NULL DEFAULT '[]',
                confidence               REAL    NOT NULL,
                status                   TEXT    NOT NULL DEFAULT 'active',
                evidence_event_ids       TEXT    NOT NULL DEFAULT '[]',
                counterevidence_event_ids TEXT   NOT NULL DEFAULT '[]',
                created_at               REAL    NOT NULL,
                updated_at               REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS inquiries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint     TEXT    NOT NULL UNIQUE,
                question        TEXT    NOT NULL,
                concept_names   TEXT    NOT NULL DEFAULT '[]',
                priority        REAL    NOT NULL DEFAULT 0.5,
                status          TEXT    NOT NULL DEFAULT 'open',
                origin          TEXT    NOT NULL,
                attempts        INTEGER NOT NULL DEFAULT 0,
                next_attempt_at REAL    NOT NULL DEFAULT 0,
                last_result     TEXT,
                created_at      REAL    NOT NULL,
                updated_at      REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                statement        TEXT    NOT NULL,
                test_method      TEXT    NOT NULL,
                concept_names    TEXT    NOT NULL DEFAULT '[]',
                confidence       REAL    NOT NULL,
                status           TEXT    NOT NULL DEFAULT 'pending',
                outcome          TEXT,
                evidence         TEXT,
                cycle_id         INTEGER,
                expected_by      REAL,
                created_at       REAL    NOT NULL,
                resolved_at      REAL
            );

            CREATE TABLE IF NOT EXISTS external_observations (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                content       TEXT    NOT NULL,
                source        TEXT    NOT NULL,
                concept_names TEXT    NOT NULL DEFAULT '[]',
                reliability   REAL    NOT NULL,
                created_at    REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS consolidation_runs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                source_event_ids TEXT    NOT NULL,
                summary          TEXT    NOT NULL,
                result_json      TEXT    NOT NULL,
                status           TEXT    NOT NULL,
                created_at       REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS self_model_entries (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence   TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cognitive_state (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_connections_status
                ON concept_connections(status);
            CREATE INDEX IF NOT EXISTS idx_thought_memory_quality
                ON thought_stream(consolidated, reliability, created_at);
            CREATE INDEX IF NOT EXISTS idx_inquiries_queue
                ON inquiries(status, next_attempt_at, priority);
            CREATE INDEX IF NOT EXISTS idx_predictions_status
                ON predictions(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_cycles_created
                ON cognitive_cycles(created_at);
        """)

        # Preserve all legacy rows while removing known graph pollution from active reasoning.
        conn.execute(
            """UPDATE concept_connections
               SET confidence = min(1.0, max(0.0, strength)),
                   updated_at = COALESCE(updated_at, created_at)
               WHERE source = 'legacy'"""
        )
        conn.execute(
            """UPDATE concept_connections
               SET status = 'archived'
               WHERE status = 'active'
                 AND (concept_a_id = concept_b_id OR relationship = 'спонтанная связь')"""
        )
        conn.execute("PRAGMA user_version = 2")
        conn.commit()

    _init_memory_fts()


def _init_memory_fts() -> None:
    try:
        with get_conn() as conn:
            conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS thought_memory_fts
                USING fts5(content, tokenize='unicode61');

                CREATE TRIGGER IF NOT EXISTS thought_memory_fts_ai
                AFTER INSERT ON thought_stream BEGIN
                    INSERT INTO thought_memory_fts(rowid, content)
                    VALUES (new.id, new.content);
                END;

                CREATE TRIGGER IF NOT EXISTS thought_memory_fts_ad
                AFTER DELETE ON thought_stream BEGIN
                    DELETE FROM thought_memory_fts WHERE rowid = old.id;
                END;

                CREATE TRIGGER IF NOT EXISTS thought_memory_fts_au
                AFTER UPDATE OF content ON thought_stream BEGIN
                    UPDATE thought_memory_fts SET content = new.content
                    WHERE rowid = old.id;
                END;
            """)
            stream_count = conn.execute("SELECT COUNT(*) FROM thought_stream").fetchone()[0]
            fts_count = conn.execute("SELECT COUNT(*) FROM thought_memory_fts").fetchone()[0]
            if stream_count != fts_count:
                conn.execute("DELETE FROM thought_memory_fts")
                conn.execute(
                    "INSERT INTO thought_memory_fts(rowid, content) "
                    "SELECT id, content FROM thought_stream"
                )
            conn.commit()
    except sqlite3.OperationalError:
        # Some local SQLite builds omit FTS5; retrieval has a LIKE fallback.
        pass


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


def get_concept_by_name_normalized(name: str) -> sqlite3.Row | None:
    needle = _norm_text(name)
    for row in list_concepts():
        if _norm_text(row["name"]) == needle:
            return row
    return None


def find_concepts_by_name_fragment(fragment: str, limit: int = 5) -> list[sqlite3.Row]:
    needle = _norm_text(fragment)
    if not needle:
        return []
    matches = [
        row for row in list_concepts()
        if needle in _norm_text(row["name"]) or _norm_text(row["name"]) in needle
    ]
    return sorted(matches, key=lambda row: (len(row["name"]), -row["real_time_added"]))[:limit]


def list_concepts() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM concepts ORDER BY real_time_added ASC"
        ).fetchall()


def list_concepts_needing_grounding(limit: int = 12) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT c.*,
                      COUNT(DISTINCT cg.grounding_id) AS grounding_count,
                      COUNT(DISTINCT CASE
                          WHEN cc.status='active' AND cc.concept_a_id<>cc.concept_b_id
                          THEN cc.id END) AS active_degree
               FROM concepts c
               LEFT JOIN concept_groundings cg ON cg.concept_id=c.id
               LEFT JOIN concept_connections cc
                 ON (cc.concept_a_id=c.id OR cc.concept_b_id=c.id)
               GROUP BY c.id
               ORDER BY grounding_count ASC, active_degree ASC, c.real_time_added DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()


def upsert_connection(
    a_id: int,
    b_id: int,
    relationship: str,
    strength: float,
    created_at: float,
    *,
    source: str,
    confidence: float,
) -> int | None:
    """Insert or revise an undirected relation after external validation."""
    if a_id == b_id:
        return None
    a_id, b_id = sorted((a_id, b_id))
    relationship = " ".join(relationship.split()).strip()
    if not relationship:
        return None
    strength = max(0.0, min(1.0, float(strength)))
    confidence = max(0.0, min(1.0, float(confidence)))

    with get_conn() as conn:
        existing = conn.execute(
            """SELECT * FROM concept_connections
               WHERE (concept_a_id=? AND concept_b_id=?)
                  OR (concept_a_id=? AND concept_b_id=?)""",
            (a_id, b_id, b_id, a_id),
        ).fetchone()
        if existing:
            prior_count = max(1, int(existing["evidence_count"]))
            weight = min(prior_count, 10)
            merged_confidence = (
                float(existing["confidence"]) * weight + confidence
            ) / (weight + 1)
            merged_strength = (
                float(existing["strength"]) * weight + strength
            ) / (weight + 1)
            replace_label = (
                confidence >= float(existing["confidence"])
                or not existing["relationship"]
                or existing["relationship"] == "спонтанная связь"
            )
            conn.execute(
                """UPDATE concept_connections
                   SET relationship=?,
                       strength=?,
                       confidence=?,
                       evidence_count=evidence_count + 1,
                       status='active',
                       source=?,
                       updated_at=?
                   WHERE id=?""",
                (
                    relationship if replace_label else existing["relationship"],
                    merged_strength,
                    merged_confidence,
                    source,
                    created_at,
                    existing["id"],
                ),
            )
            conn.commit()
            return int(existing["id"])

        cur = conn.execute(
            """INSERT INTO concept_connections
               (concept_a_id, concept_b_id, relationship, strength, created_at,
                status, confidence, evidence_count, contradiction_count, source, updated_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?, 1, 0, ?, ?)""",
            (
                a_id,
                b_id,
                relationship,
                strength,
                created_at,
                confidence,
                source,
                created_at,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def insert_connection(a_id: int, b_id: int, relationship: str,
                      strength: float, created_at: float) -> int | None:
    return upsert_connection(
        a_id,
        b_id,
        relationship,
        strength,
        created_at,
        source="legacy_api",
        confidence=strength,
    )


def get_connections_for(concept_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT cc.*, c.name as other_name
               FROM concept_connections cc
               JOIN concepts c ON (
                 CASE WHEN cc.concept_a_id = ? THEN cc.concept_b_id ELSE cc.concept_a_id END = c.id
               )
               WHERE (cc.concept_a_id = ? OR cc.concept_b_id = ?)
                 AND cc.status = 'active'
                 AND cc.concept_a_id <> cc.concept_b_id""",
            (concept_id, concept_id, concept_id),
        ).fetchall()


def list_connections() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM concept_connections
               WHERE status='active' AND concept_a_id <> concept_b_id"""
        ).fetchall()


def get_connection_between(a_id: int, b_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM concept_connections
               WHERE (concept_a_id=? AND concept_b_id=?)
                  OR (concept_a_id=? AND concept_b_id=?)""",
            (a_id, b_id, b_id, a_id),
        ).fetchone()


def record_relation_evidence(
    concept_a_id: int,
    concept_b_id: int,
    relationship: str,
    verdict: str,
    confidence: float,
    created_at: float,
    *,
    connection_id: int | None = None,
    source_event_id: int | None = None,
    cycle_id: int | None = None,
    reason: str | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO relation_evidence
               (connection_id, concept_a_id, concept_b_id, relationship, verdict,
                confidence, source_event_id, cycle_id, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                connection_id,
                concept_a_id,
                concept_b_id,
                relationship,
                verdict,
                max(0.0, min(1.0, float(confidence))),
                source_event_id,
                cycle_id,
                reason,
                created_at,
            ),
        )
        normalized_confidence = max(0.0, min(1.0, float(confidence)))
        if (
            verdict in {"reject", "contradict"}
            and connection_id is not None
            and normalized_confidence >= 0.6
        ):
            conn.execute(
                """UPDATE concept_connections
                   SET contradiction_count=contradiction_count + 1,
                       status=CASE
                           WHEN contradiction_count + 1 >= 3 THEN 'archived'
                           ELSE status
                       END,
                       source=CASE
                           WHEN contradiction_count + 1 >= 3 THEN 'critic_retracted'
                           ELSE source
                       END,
                       updated_at=?
                   WHERE id=?""",
                (created_at, connection_id),
            )
        conn.commit()
        return int(cur.lastrowid)


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


def insert_grounding_excerpt(title: str, author: str | None, source: str | None,
                             excerpt: str, mind_time: str, created_at: float) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO grounding_excerpts
               (title, author, source, excerpt, mind_time, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, author, source, excerpt, mind_time, created_at),
        )
        conn.commit()
        return cur.lastrowid


def link_grounding_to_concept(concept_id: int, grounding_id: int,
                              note: str | None, created_at: float) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO concept_groundings
               (concept_id, grounding_id, note, created_at)
               VALUES (?, ?, ?, ?)""",
            (concept_id, grounding_id, note, created_at),
        )
        conn.commit()


def get_groundings_for_concept(concept_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT ge.*, cg.note
               FROM concept_groundings cg
               JOIN grounding_excerpts ge ON ge.id = cg.grounding_id
               WHERE cg.concept_id = ?
               ORDER BY ge.created_at DESC""",
            (concept_id,),
        ).fetchall()


def list_groundings(limit: int = 100, offset: int = 0) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT ge.*,
                      GROUP_CONCAT(c.name, ', ') AS concept_names
               FROM grounding_excerpts ge
               LEFT JOIN concept_groundings cg ON cg.grounding_id = ge.id
               LEFT JOIN concepts c ON c.id = cg.concept_id
               GROUP BY ge.id
               ORDER BY ge.created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()


def find_groundings_for_concept_names(names: list[str], limit: int = 6) -> list[sqlite3.Row]:
    names = [n for n in names if n]
    if not names:
        return []
    placeholders = ",".join("?" for _ in names)
    with get_conn() as conn:
        return conn.execute(
            f"""SELECT ge.*, cg.note, c.name AS concept_name
                FROM concept_groundings cg
                JOIN concepts c ON c.id = cg.concept_id
                JOIN grounding_excerpts ge ON ge.id = cg.grounding_id
                WHERE c.name IN ({placeholders})
                ORDER BY ge.created_at DESC
                LIMIT ?""",
            (*names, limit),
        ).fetchall()


def insert_working_definition(concept_id: int, definition: str,
                              tension: str | None, source: str,
                              source_ref_id: int | None, confidence: float,
                              mind_time: str, created_at: float) -> int:
    confidence = max(0.0, min(1.0, float(confidence)))
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO concept_working_definitions
               (concept_id, definition, tension, source, source_ref_id,
                confidence, mind_time, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (concept_id, definition, tension, source, source_ref_id,
             confidence, mind_time, created_at),
        )
        conn.commit()
        return cur.lastrowid


def get_working_definitions_for_concept(concept_id: int, limit: int = 10) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT cwd.*, c.name AS concept_name
               FROM concept_working_definitions cwd
               JOIN concepts c ON c.id = cwd.concept_id
               WHERE cwd.concept_id = ?
               ORDER BY cwd.created_at DESC
               LIMIT ?""",
            (concept_id, limit),
        ).fetchall()


def get_latest_working_definitions_for_names(names: list[str], limit_per_concept: int = 2) -> list[sqlite3.Row]:
    result: list[sqlite3.Row] = []
    for name in names:
        concept = get_concept_by_name_normalized(name)
        if not concept:
            continue
        result.extend(get_working_definitions_for_concept(concept["id"], limit_per_concept))
    return result


def insert_stream_event(
    mind_time: str,
    event_type: str,
    content: str,
    concepts: list[str],
    created_at: float,
    *,
    salience: float = 0.5,
    reliability: float = 0.5,
    consolidated: bool = False,
    cycle_id: int | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO thought_stream
               (mind_time, type, content, concepts_involved, created_at,
                salience, reliability, consolidated, cycle_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mind_time,
                event_type,
                content,
                json.dumps(concepts, ensure_ascii=False),
                created_at,
                max(0.0, min(1.0, float(salience))),
                max(0.0, min(1.0, float(reliability))),
                1 if consolidated else 0,
                cycle_id,
            ),
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


def insert_neologism(word: str, explanation: str, source: str,
                     concept_id: int | None, mind_time: str, created_at: float) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO neologisms (word, explanation, source, concept_id, mind_time, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (word, explanation, source, concept_id, mind_time, created_at),
        )
        conn.commit()
        return cur.lastrowid


def list_neologisms(limit: int = 100, offset: int = 0) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM neologisms ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def get_last_autonomous_time() -> float | None:
    """Return real_time_added of the most recently created autonomous concept, or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(real_time_added) as t FROM concepts WHERE is_autonomous=1"
        ).fetchone()
        return float(row["t"]) if row and row["t"] is not None else None


# ── Cognitive memory and evaluation ───────────────────────────────────────

def search_memory_events(terms: list[str], limit: int = 40) -> list[dict]:
    cleaned = [" ".join(term.split()).strip() for term in terms if term.strip()]
    rows: list[dict] = []
    if cleaned:
        match_query = " OR ".join(
            f'"{term.replace(chr(34), chr(34) * 2)}"' for term in cleaned[:12]
        )
        try:
            with get_conn() as conn:
                rows = [
                    dict(row)
                    for row in conn.execute(
                        """SELECT ts.*, bm25(thought_memory_fts) AS lexical_rank
                           FROM thought_memory_fts
                           JOIN thought_stream ts ON ts.id = thought_memory_fts.rowid
                           WHERE thought_memory_fts MATCH ?
                           ORDER BY lexical_rank
                           LIMIT ?""",
                        (match_query, limit),
                    ).fetchall()
                ]
        except sqlite3.OperationalError:
            rows = []

    if not rows and cleaned:
        clauses = " OR ".join("content LIKE ?" for _ in cleaned[:8])
        params = [f"%{term}%" for term in cleaned[:8]]
        with get_conn() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    f"""SELECT *, 0.0 AS lexical_rank
                        FROM thought_stream
                        WHERE {clauses}
                        ORDER BY created_at DESC
                        LIMIT ?""",
                    (*params, limit),
                ).fetchall()
            ]
    return rows


def list_recent_high_quality_events(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """SELECT *, 0.0 AS lexical_rank
                   FROM thought_stream
                   WHERE reliability >= 0.55 OR salience >= 0.7
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        ]


def list_unconsolidated_events(limit: int = 12) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM thought_stream
               WHERE consolidated=0
                 AND reliability >= 0.6
                 AND type IN ('cognitive', 'contemplation', 'observation', 'feedback')
               ORDER BY created_at ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()


def mark_events_consolidated(event_ids: list[int]) -> None:
    if not event_ids:
        return
    placeholders = ",".join("?" for _ in event_ids)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE thought_stream SET consolidated=1 WHERE id IN ({placeholders})",
            event_ids,
        )
        conn.commit()


def insert_cognitive_cycle(
    trigger: str,
    focus: str,
    candidate: dict,
    critique: dict,
    memory_event_ids: list[int],
    verdict: str,
    reliability: float,
    created_at: float,
    inquiry_id: int | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO cognitive_cycles
               (trigger, focus, inquiry_id, candidate_json, critique_json,
                memory_event_ids, verdict, reliability, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trigger,
                focus,
                inquiry_id,
                json.dumps(candidate, ensure_ascii=False),
                json.dumps(critique, ensure_ascii=False),
                json.dumps(memory_event_ids),
                verdict,
                max(0.0, min(1.0, float(reliability))),
                created_at,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_cognitive_cycles(limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM cognitive_cycles
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()


def create_inquiry(
    question: str,
    concept_names: list[str],
    priority: float,
    origin: str,
    created_at: float,
) -> int:
    question = " ".join(question.split()).strip()
    if not question:
        raise ValueError("Inquiry question cannot be empty")
    fingerprint = _fingerprint(question)
    priority = max(0.0, min(1.0, float(priority)))
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM inquiries WHERE fingerprint=?", (fingerprint,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE inquiries
                   SET priority=max(priority, ?),
                       concept_names=?,
                       status=CASE WHEN status='resolved' THEN status ELSE 'open' END,
                       updated_at=?
                   WHERE id=?""",
                (
                    priority,
                    json.dumps(concept_names, ensure_ascii=False),
                    created_at,
                    existing["id"],
                ),
            )
            conn.commit()
            return int(existing["id"])
        cur = conn.execute(
            """INSERT INTO inquiries
               (fingerprint, question, concept_names, priority, status, origin,
                attempts, next_attempt_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'open', ?, 0, 0, ?, ?)""",
            (
                fingerprint,
                question,
                json.dumps(concept_names, ensure_ascii=False),
                priority,
                origin,
                created_at,
                created_at,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_next_inquiry(now: float) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM inquiries
               WHERE status IN ('open', 'blocked') AND next_attempt_at <= ?
               ORDER BY priority DESC, updated_at ASC
               LIMIT 1""",
            (now,),
        ).fetchone()


def record_inquiry_attempt(
    inquiry_id: int,
    result: str,
    resolved: bool,
    now: float,
) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT attempts FROM inquiries WHERE id=?", (inquiry_id,)
        ).fetchone()
        if not row:
            return
        attempts = int(row["attempts"]) + 1
        if resolved:
            status = "resolved"
            next_attempt_at = now
        elif attempts >= 3:
            status = "blocked"
            next_attempt_at = now + 24 * 3600
        else:
            status = "open"
            next_attempt_at = now + min(6 * 3600 * attempts, 24 * 3600)
        conn.execute(
            """UPDATE inquiries
               SET attempts=?, status=?, next_attempt_at=?, last_result=?, updated_at=?
               WHERE id=?""",
            (attempts, status, next_attempt_at, result[:2000], now, inquiry_id),
        )
        conn.commit()


def list_inquiries(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if status:
            return conn.execute(
                """SELECT * FROM inquiries WHERE status=?
                   ORDER BY priority DESC, updated_at DESC LIMIT ? OFFSET ?""",
                (status, limit, offset),
            ).fetchall()
        return conn.execute(
            """SELECT * FROM inquiries
               ORDER BY priority DESC, updated_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()


def upsert_belief(
    statement: str,
    concept_names: list[str],
    confidence: float,
    evidence_event_ids: list[int],
    now: float,
) -> int:
    statement = " ".join(statement.split()).strip()
    if not statement:
        raise ValueError("Belief statement cannot be empty")
    confidence = max(0.0, min(1.0, float(confidence)))
    fingerprint = _fingerprint(statement)
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM beliefs WHERE fingerprint=?", (fingerprint,)
        ).fetchone()
        if existing:
            prior_evidence = json.loads(existing["evidence_event_ids"] or "[]")
            combined = list(dict.fromkeys([*prior_evidence, *evidence_event_ids]))
            merged = (float(existing["confidence"]) + confidence) / 2
            conn.execute(
                """UPDATE beliefs
                   SET confidence=?, concept_names=?, evidence_event_ids=?,
                       status='active', updated_at=?
                   WHERE id=?""",
                (
                    merged,
                    json.dumps(concept_names, ensure_ascii=False),
                    json.dumps(combined),
                    now,
                    existing["id"],
                ),
            )
            conn.commit()
            return int(existing["id"])
        cur = conn.execute(
            """INSERT INTO beliefs
               (fingerprint, statement, concept_names, confidence, status,
                evidence_event_ids, counterevidence_event_ids, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'active', ?, '[]', ?, ?)""",
            (
                fingerprint,
                statement,
                json.dumps(concept_names, ensure_ascii=False),
                confidence,
                json.dumps(evidence_event_ids),
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_beliefs(
    status: str = "active",
    limit: int = 100,
    offset: int = 0,
) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM beliefs WHERE status=?
               ORDER BY confidence DESC, updated_at DESC LIMIT ? OFFSET ?""",
            (status, limit, offset),
        ).fetchall()


def insert_prediction(
    statement: str,
    test_method: str,
    concept_names: list[str],
    confidence: float,
    created_at: float,
    *,
    cycle_id: int | None = None,
    expected_by: float | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO predictions
               (statement, test_method, concept_names, confidence, status,
                cycle_id, expected_by, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (
                statement.strip(),
                test_method.strip(),
                json.dumps(concept_names, ensure_ascii=False),
                max(0.0, min(1.0, float(confidence))),
                cycle_id,
                expected_by,
                created_at,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_prediction(prediction_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM predictions WHERE id=?", (prediction_id,)
        ).fetchone()


def resolve_prediction(
    prediction_id: int,
    outcome: str,
    evidence: str,
    resolved_at: float,
) -> bool:
    if outcome not in {"confirmed", "disconfirmed", "inconclusive"}:
        raise ValueError("Invalid prediction outcome")
    with get_conn() as conn:
        cur = conn.execute(
            """UPDATE predictions
               SET status='resolved', outcome=?, evidence=?, resolved_at=?
               WHERE id=? AND status='pending'""",
            (outcome, evidence.strip(), resolved_at, prediction_id),
        )
        conn.commit()
        return cur.rowcount > 0


def list_predictions(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if status:
            return conn.execute(
                """SELECT * FROM predictions WHERE status=?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (status, limit, offset),
            ).fetchall()
        return conn.execute(
            """SELECT * FROM predictions
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()


def insert_external_observation(
    content: str,
    source: str,
    concept_names: list[str],
    reliability: float,
    created_at: float,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO external_observations
               (content, source, concept_names, reliability, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                content.strip(),
                source.strip(),
                json.dumps(concept_names, ensure_ascii=False),
                max(0.0, min(1.0, float(reliability))),
                created_at,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_external_observations(limit: int = 50) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM external_observations
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def insert_consolidation_run(
    source_event_ids: list[int],
    summary: str,
    result: dict,
    status: str,
    created_at: float,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO consolidation_runs
               (source_event_ids, summary, result_json, status, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                json.dumps(source_event_ids),
                summary,
                json.dumps(result, ensure_ascii=False),
                status,
                created_at,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_consolidation_runs(limit: int = 20) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM consolidation_runs
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def upsert_self_model_entry(
    key: str,
    value: str,
    confidence: float,
    evidence: str,
    updated_at: float,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO self_model_entries
               (key, value, confidence, evidence, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value=excluded.value,
                   confidence=excluded.confidence,
                   evidence=excluded.evidence,
                   updated_at=excluded.updated_at""",
            (
                key,
                value,
                max(0.0, min(1.0, float(confidence))),
                evidence,
                updated_at,
            ),
        )
        conn.commit()


def list_self_model_entries() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM self_model_entries ORDER BY key"
        ).fetchall()


def set_cognitive_state(key: str, value: str, updated_at: float) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO cognitive_state (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, updated_at),
        )
        conn.commit()


def get_cognitive_state(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM cognitive_state WHERE key=?", (key,)
        ).fetchone()
        return str(row["value"]) if row else None


def get_cognitive_metrics() -> dict:
    with get_conn() as conn:
        concepts = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
        active_edges = conn.execute(
            """SELECT COUNT(*) FROM concept_connections
               WHERE status='active' AND concept_a_id<>concept_b_id"""
        ).fetchone()[0]
        archived_edges = conn.execute(
            "SELECT COUNT(*) FROM concept_connections WHERE status='archived'"
        ).fetchone()[0]
        grounded = conn.execute(
            "SELECT COUNT(DISTINCT concept_id) FROM concept_groundings"
        ).fetchone()[0]
        defined = conn.execute(
            "SELECT COUNT(DISTINCT concept_id) FROM concept_working_definitions"
        ).fetchone()[0]
        open_inquiries = conn.execute(
            "SELECT COUNT(*) FROM inquiries WHERE status='open'"
        ).fetchone()[0]
        pending_predictions = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE status='pending'"
        ).fetchone()[0]
        active_self_loops = conn.execute(
            """SELECT COUNT(*) FROM concept_connections
               WHERE status='active' AND concept_a_id=concept_b_id"""
        ).fetchone()[0]
        active_fallback_edges = conn.execute(
            """SELECT COUNT(*) FROM concept_connections
               WHERE status='active' AND relationship='спонтанная связь'"""
        ).fetchone()[0]
        cycles = conn.execute("SELECT COUNT(*) FROM cognitive_cycles").fetchone()[0]
        accepted_cycles = conn.execute(
            "SELECT COUNT(*) FROM cognitive_cycles WHERE verdict IN ('accept', 'revise')"
        ).fetchone()[0]
        resolved = conn.execute(
            """SELECT outcome, confidence FROM predictions
               WHERE status='resolved' AND outcome IN ('confirmed', 'disconfirmed')"""
        ).fetchall()
        brier = None
        if resolved:
            errors = []
            for row in resolved:
                target = 1.0 if row["outcome"] == "confirmed" else 0.0
                errors.append((float(row["confidence"]) - target) ** 2)
            brier = sum(errors) / len(errors)
        max_edges = concepts * (concepts - 1) / 2 if concepts > 1 else 0
        return {
            "concepts": concepts,
            "active_edges": active_edges,
            "archived_edges": archived_edges,
            "active_graph_density": active_edges / max_edges if max_edges else 0.0,
            "grounded_concepts": grounded,
            "grounding_coverage": grounded / concepts if concepts else 0.0,
            "defined_concepts": defined,
            "definition_coverage": defined / concepts if concepts else 0.0,
            "open_inquiries": open_inquiries,
            "pending_predictions": pending_predictions,
            "active_self_loops": active_self_loops,
            "active_fallback_edges": active_fallback_edges,
            "cognitive_cycles": cycles,
            "accepted_cycle_rate": accepted_cycles / cycles if cycles else None,
            "resolved_predictions": len(resolved),
            "prediction_brier_score": brier,
        }
