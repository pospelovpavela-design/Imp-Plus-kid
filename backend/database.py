"""
database.py — canonical module name per spec file structure.
Re-exports everything from db.py so both names work interchangeably.
"""
from db import *  # noqa: F401, F403
from db import (
    get_conn, init_db,
    get_mind_state, create_mind_state,
    insert_concept, concept_exists, get_concept_by_id, get_concept_by_name, list_concepts,
    insert_connection, get_connections_for, list_connections,
    insert_processing_log, get_processing_logs,
    insert_stream_event, get_stream_events,
    insert_contemplation, get_contemplations,
    milestone_exists, insert_milestone, list_milestones,
    update_concept_label,
)
