"""SQLite operational store for draft and weekly league events."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS managers (
    manager_id INTEGER PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    is_user INTEGER NOT NULL DEFAULT 0 CHECK (is_user IN (0, 1))
);

CREATE TABLE IF NOT EXISTS players (
    player_code INTEGER PRIMARY KEY,
    current_fpl_id INTEGER,
    name TEXT NOT NULL,
    position TEXT NOT NULL CHECK (position IN ('GK', 'DEF', 'MID', 'FWD')),
    current_team TEXT,
    selectable INTEGER NOT NULL DEFAULT 1 CHECK (selectable IN (0, 1))
);

CREATE TABLE IF NOT EXISTS draft_picks (
    draft_id TEXT NOT NULL,
    pick_number INTEGER NOT NULL CHECK (pick_number > 0),
    round_number INTEGER NOT NULL CHECK (round_number > 0),
    manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
    player_code INTEGER NOT NULL REFERENCES players(player_code),
    picked_at TEXT NOT NULL,
    PRIMARY KEY (draft_id, pick_number),
    UNIQUE (draft_id, player_code)
);

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    season TEXT NOT NULL,
    gameweek INTEGER,
    horizon INTEGER NOT NULL CHECK (horizon > 0),
    player_code INTEGER NOT NULL REFERENCES players(player_code),
    model_version TEXT NOT NULL,
    appearance_probability REAL,
    start_probability REAL,
    expected_minutes REAL,
    points_p10 REAL,
    points_p50 REAL,
    points_p90 REAL,
    UNIQUE (created_at, horizon, player_code, model_version)
);

CREATE TABLE IF NOT EXISTS roster_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    season TEXT NOT NULL,
    gameweek INTEGER,
    manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
    player_code INTEGER NOT NULL REFERENCES players(player_code),
    event_type TEXT NOT NULL CHECK (
        event_type IN ('draft_add', 'waiver_add', 'waiver_drop', 'free_agent_add',
                       'free_agent_drop', 'trade_add', 'trade_drop')
    ),
    related_event_id INTEGER REFERENCES roster_events(event_id),
    note TEXT
);

CREATE TABLE IF NOT EXISTS waiver_claims (
    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    submitted_at TEXT NOT NULL,
    season TEXT NOT NULL,
    gameweek INTEGER NOT NULL,
    manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
    priority INTEGER NOT NULL CHECK (priority > 0),
    add_player_code INTEGER NOT NULL REFERENCES players(player_code),
    drop_player_code INTEGER NOT NULL REFERENCES players(player_code),
    outcome TEXT NOT NULL CHECK (outcome IN ('pending', 'successful', 'failed', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposed_at TEXT NOT NULL,
    resolved_at TEXT,
    proposer_manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
    recipient_manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
    status TEXT NOT NULL CHECK (status IN ('proposed', 'accepted', 'rejected', 'cancelled', 'vetoed')),
    note TEXT
);

CREATE TABLE IF NOT EXISTS trade_players (
    trade_id INTEGER NOT NULL REFERENCES trades(trade_id) ON DELETE CASCADE,
    from_manager_id INTEGER NOT NULL REFERENCES managers(manager_id),
    player_code INTEGER NOT NULL REFERENCES players(player_code),
    PRIMARY KEY (trade_id, player_code)
);

CREATE INDEX IF NOT EXISTS idx_predictions_player_week
    ON predictions (player_code, season, gameweek, horizon);
CREATE INDEX IF NOT EXISTS idx_roster_events_manager_week
    ON roster_events (manager_id, season, gameweek, occurred_at);
"""


def connect_database(path: str | Path) -> sqlite3.Connection:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(destination)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize_database(path: str | Path) -> None:
    connection = connect_database(path)
    try:
        with connection:
            connection.executescript(SCHEMA_SQL)
            connection.execute(
                "INSERT INTO schema_metadata(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            connection.executemany(
                "INSERT OR IGNORE INTO managers(manager_id, label, is_user) VALUES(?, ?, ?)",
                ((1, "You", 1), (2, "Friend A", 0), (3, "Friend B", 0), (4, "Friend C", 0)),
            )
    finally:
        connection.close()
