"""
SQLite database helpers.

Schema
------
venues           - cached venue records from Prism
stages           - stages belonging to each venue
events           - cached event summaries from Prism
run_of_show_items- items fetched from the Prism run-of-show API
                   PLUS locally-created items (source='local')

Duplicate prevention on run_of_show_items is enforced by a UNIQUE
constraint on (event_id, title, occurs_at_norm, stage_id_norm) where
*_norm columns collapse NULLs to sentinel values so SQLite's NULL≠NULL
rule doesn't undermine the constraint.
"""

import sqlite3
from typing import Optional


_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS venues (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    timezone    TEXT,
    capacity    INTEGER,
    city        TEXT,
    state       TEXT,
    country     TEXT,
    address     TEXT,
    currency    TEXT,
    stages_json TEXT,          -- JSON array of stage objects
    raw_json    TEXT,          -- full Prism API response
    synced_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stages (
    id       INTEGER PRIMARY KEY,
    venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    name     TEXT    NOT NULL,
    active   INTEGER NOT NULL DEFAULT 1,
    capacity INTEGER,
    color    TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id                  INTEGER PRIMARY KEY,
    name                TEXT    NOT NULL,
    event_status        INTEGER,        -- 0=HOLD 2=CONFIRMED 3=IN_SETTLEMENT 4=SETTLED
    event_status_string TEXT,
    first_date          TEXT,           -- ISO date string (YYYY-MM-DD or ISO datetime)
    last_date           TEXT,
    date_range_string   TEXT,
    venue_id            INTEGER,
    venue_name          TEXT,
    venue_address       TEXT,
    venue_city          TEXT,
    venue_state         TEXT,
    stage_names         TEXT,
    is_archived         INTEGER NOT NULL DEFAULT 0,
    is_rental           INTEGER NOT NULL DEFAULT 0,
    tour_name           TEXT,
    number_of_shows     INTEGER,
    capacity            INTEGER,
    event_last_updated  TEXT,
    event_created_date  TEXT,
    age_limit           TEXT,
    ticketing_url       TEXT,
    dates_json          TEXT,           -- JSON [{date,allDay,startTime,endTime,stageName},...]
    raw_json            TEXT,
    synced_at           TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (venue_id) REFERENCES venues(id)
);

CREATE TABLE IF NOT EXISTS run_of_show_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prism_id        INTEGER,            -- API-assigned ID (NULL for local items)
    title           TEXT    NOT NULL,
    occurs_at       TEXT    NOT NULL,   -- ISO datetime from API
    finishes_at     TEXT,               -- ISO datetime from API
    event_id        INTEGER,
    event_name      TEXT,
    event_status    INTEGER,
    venue_id        INTEGER,
    venue_name      TEXT,
    stage_id        INTEGER,
    stage_name      TEXT,
    event_description TEXT,
    source          TEXT    NOT NULL DEFAULT 'api',  -- 'api' | 'local'
    raw_json        TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    synced_at       TEXT,               -- NULL for local items

    -- Normalised columns used for the duplicate-prevention constraint.
    -- We coalesce NULLs so that (event_id=1, title='Doors', occurs_at='...', stage_id=NULL)
    -- correctly conflicts with itself on re-insert.
    event_id_norm   INTEGER NOT NULL GENERATED ALWAYS AS (COALESCE(event_id, -1)) VIRTUAL,
    stage_id_norm   INTEGER NOT NULL GENERATED ALWAYS AS (COALESCE(stage_id, -1)) VIRTUAL,

    UNIQUE (event_id_norm, title, occurs_at, stage_id_norm)
);

CREATE INDEX IF NOT EXISTS idx_events_venue    ON events(venue_id);
CREATE INDEX IF NOT EXISTS idx_events_status   ON events(event_status);
CREATE INDEX IF NOT EXISTS idx_events_date     ON events(first_date);
CREATE INDEX IF NOT EXISTS idx_ros_event       ON run_of_show_items(event_id);
CREATE INDEX IF NOT EXISTS idx_ros_venue       ON run_of_show_items(venue_id);
CREATE INDEX IF NOT EXISTS idx_ros_occurs      ON run_of_show_items(occurs_at);
CREATE INDEX IF NOT EXISTS idx_stages_venue    ON stages(venue_id);
"""


def get_db(db_path: str) -> sqlite3.Connection:
    """Open (or reuse) a database connection with row_factory."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    """Create tables if they don't exist."""
    conn = get_db(db_path)
    conn.executescript(_DDL)
    # Additive migrations for existing databases
    try:
        conn.execute("ALTER TABLE events ADD COLUMN dates_json TEXT")
    except Exception:
        pass  # column already exists
    conn.commit()
    conn.close()


# ── Settings helpers ──────────────────────────────────────────────────────────

def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    """Return the value for *key* from the settings table, or *default*."""
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if (row and row["value"] is not None) else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Upsert a key-value pair in the settings table."""
    conn.execute(
        """
        INSERT INTO settings (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value      = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, value),
    )


# ── Upsert helpers ────────────────────────────────────────────────────────────

def upsert_venue(conn: sqlite3.Connection, venue: dict) -> None:
    """Insert or replace a venue (keyed on id)."""
    import json
    stages = venue.get("stages", [])
    conn.execute(
        """
        INSERT INTO venues
            (id, name, active, timezone, capacity, city, state, country,
             address, currency, stages_json, raw_json, synced_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            name        = excluded.name,
            active      = excluded.active,
            timezone    = excluded.timezone,
            capacity    = excluded.capacity,
            city        = excluded.city,
            state       = excluded.state,
            country     = excluded.country,
            address     = excluded.address,
            currency    = excluded.currency,
            stages_json = excluded.stages_json,
            raw_json    = excluded.raw_json,
            synced_at   = excluded.synced_at
        """,
        (
            venue["id"],
            venue.get("name", ""),
            1 if venue.get("active", True) else 0,
            venue.get("timezone"),
            venue.get("capacity"),
            venue.get("city_short") or venue.get("city_long"),
            venue.get("state_short") or venue.get("state_long"),
            venue.get("country_short") or venue.get("country_long"),
            venue.get("address_1_long") or venue.get("address_1_short"),
            venue.get("currency"),
            json.dumps(stages),
            json.dumps(venue),
        ),
    )
    # Sync stages sub-table
    conn.execute("DELETE FROM stages WHERE venue_id = ?", (venue["id"],))
    for s in stages:
        conn.execute(
            """
            INSERT OR REPLACE INTO stages (id, venue_id, name, active, capacity, color)
            VALUES (?,?,?,?,?,?)
            """,
            (
                s["id"],
                venue["id"],
                s.get("name", ""),
                1 if s.get("active", True) else 0,
                s.get("capacity"),
                s.get("color"),
            ),
        )


def upsert_event(conn: sqlite3.Connection, event: dict) -> None:
    """Insert or replace an event summary (keyed on id)."""
    import json
    conn.execute(
        """
        INSERT INTO events
            (id, name, event_status, event_status_string, first_date, last_date,
             date_range_string, venue_id, venue_name, venue_address, venue_city,
             venue_state, stage_names, is_archived, is_rental, tour_name,
             number_of_shows, capacity, event_last_updated, event_created_date,
             age_limit, ticketing_url, dates_json, raw_json, synced_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            name                = excluded.name,
            event_status        = excluded.event_status,
            event_status_string = excluded.event_status_string,
            first_date          = excluded.first_date,
            last_date           = excluded.last_date,
            date_range_string   = excluded.date_range_string,
            venue_id            = excluded.venue_id,
            venue_name          = excluded.venue_name,
            venue_address       = excluded.venue_address,
            venue_city          = excluded.venue_city,
            venue_state         = excluded.venue_state,
            stage_names         = excluded.stage_names,
            is_archived         = excluded.is_archived,
            is_rental           = excluded.is_rental,
            tour_name           = excluded.tour_name,
            number_of_shows     = excluded.number_of_shows,
            capacity            = excluded.capacity,
            event_last_updated  = excluded.event_last_updated,
            event_created_date  = excluded.event_created_date,
            age_limit           = excluded.age_limit,
            ticketing_url       = excluded.ticketing_url,
            dates_json          = excluded.dates_json,
            raw_json            = excluded.raw_json,
            synced_at           = excluded.synced_at
        """,
        (
            event["id"],
            event.get("name", ""),
            event.get("event_status"),
            event.get("event_status_string"),
            _date_str(event.get("first_date")),
            _date_str(event.get("last_date")),
            event.get("date_range_string"),
            event.get("venue_id"),
            event.get("venue_name"),
            event.get("venue_address"),
            event.get("venue_city"),
            event.get("venue_state"),
            event.get("stage_names"),
            1 if event.get("is_archived") else 0,
            1 if event.get("is_rental") else 0,
            event.get("tour_name"),
            event.get("number_of_shows"),
            event.get("capacity"),
            _date_str(event.get("event_last_updated")),
            _date_str(event.get("event_created_date")),
            event.get("age_limit"),
            event.get("ticketing_url"),
            json.dumps(event.get("dates") or []),
            json.dumps(event),
        ),
    )


def upsert_ros_item(conn: sqlite3.Connection, item: dict) -> Optional[int]:
    """
    Insert a run-of-show item.  Returns the row id on success, or None if
    the item already exists (duplicate).  Raises on other DB errors.
    """
    import json
    event = item.get("event") or {}
    venue = item.get("venue") or {}
    stage = item.get("stage") or {}
    try:
        cursor = conn.execute(
            """
            INSERT INTO run_of_show_items
                (prism_id, title, occurs_at, finishes_at, event_id, event_name,
                 event_status, venue_id, venue_name, stage_id, stage_name,
                 event_description, source, raw_json, synced_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))
            """,
            (
                item.get("id"),             # prism_id (None for local)
                item.get("title", ""),
                item.get("occurs_at", ""),
                item.get("finishes_at"),
                event.get("id"),
                event.get("name"),
                event.get("confirmed"),
                venue.get("id"),
                venue.get("name"),
                stage.get("id"),
                stage.get("name"),
                item.get("event_description"),
                item.get("source", "api"),
                json.dumps(item) if item.get("source", "api") == "api" else None,
            ),
        )
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def _date_str(val) -> Optional[str]:
    """Normalise a date value (string, None) to a plain ISO string."""
    if val is None:
        return None
    return str(val)
