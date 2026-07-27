import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_turns (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'local-user',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS desires (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'local-user',
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_turn_id TEXT REFERENCES conversation_turns(id),
    last_touched_turn_id TEXT REFERENCES conversation_turns(id),
    supersedes_id TEXT REFERENCES desires(id)
);

CREATE TABLE IF NOT EXISTS desire_events (
    id TEXT PRIMARY KEY,
    desire_id TEXT,
    op TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    diff_json TEXT NOT NULL,
    raw_llm_response TEXT NOT NULL,
    turn_id TEXT REFERENCES conversation_turns(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_log (
    id TEXT PRIMARY KEY,
    action_name TEXT NOT NULL,
    params_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    success INTEGER NOT NULL,
    turn_id TEXT REFERENCES conversation_turns(id),
    related_desire_ids_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capability_providers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'local-user',
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    transport_json TEXT NOT NULL,
    status TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    decided_at TEXT,
    last_connected_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS capability_tools (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL REFERENCES capability_providers(id),
    tool_name TEXT NOT NULL,
    description TEXT NOT NULL,
    input_schema_json TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    UNIQUE(provider_id, tool_name)
);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
