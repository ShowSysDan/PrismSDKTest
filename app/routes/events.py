"""
Events endpoints.

GET  /api/events           - Upcoming events (default: next 30 days from cache)
GET  /api/events/by-venue  - Events grouped by venue
GET  /api/events/<id>      - Single event detail (from cache)
"""

from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request

from ..database import get_db

events_bp = Blueprint("events", __name__)

# ── Status label map ──────────────────────────────────────────────────────────
_STATUS = {0: "HOLD", 2: "CONFIRMED", 3: "IN_SETTLEMENT", 4: "SETTLED"}


def _row_to_dict(row) -> dict:
    return dict(row)


def _add_status_label(event: dict) -> dict:
    event["status_label"] = _STATUS.get(event.get("event_status"), "UNKNOWN")
    return event


# ── Routes ─────────────────────────────────────────────────────────────────────

@events_bp.get("")
def list_events():
    """
    Return upcoming events from the local cache.

    Query parameters
    ----------------
    days : int (default 30)
        How many days ahead to look.
    status : int
        Filter to a specific EventStatus value (0/2/3/4).
        May be repeated: ?status=0&status=2
    venue_id : int
        Filter to events at a specific venue.

    Returns
    -------
    JSON object
        {
          "events": [...],
          "total": <int>,
          "window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        }
    """
    days = int(request.args.get("days", current_app.config["DEFAULT_LOOKAHEAD_DAYS"]))
    today = date.today()
    end_date = today + timedelta(days=days)

    status_filters = request.args.getlist("status", type=int)
    venue_id = request.args.get("venue_id", type=int)

    db = get_db(current_app.config["DATABASE_PATH"])

    query = """
        SELECT * FROM events
        WHERE (first_date >= ? OR last_date >= ?)
          AND first_date <= ?
    """
    params: list = [str(today), str(today), str(end_date)]

    if status_filters:
        placeholders = ",".join("?" * len(status_filters))
        query += f" AND event_status IN ({placeholders})"
        params.extend(status_filters)

    if venue_id:
        query += " AND venue_id = ?"
        params.append(venue_id)

    query += " ORDER BY first_date ASC"

    rows = db.execute(query, params).fetchall()
    events = [_add_status_label(_row_to_dict(r)) for r in rows]

    return jsonify(
        events=events,
        total=len(events),
        window={"start": str(today), "end": str(end_date)},
    )


@events_bp.get("/by-venue")
def events_by_venue():
    """
    Return upcoming events grouped by venue.

    Query parameters
    ----------------
    days : int (default 30)
        How many days ahead to look.
    status : int
        Filter to a specific EventStatus value. May be repeated.

    Returns
    -------
    JSON object
        {
          "venues": [
            {
              "venue_id": <int|null>,
              "venue_name": <str>,
              "venue_city": <str>,
              "venue_state": <str>,
              "event_count": <int>,
              "events": [...]
            },
            ...
          ],
          "total_events": <int>,
          "window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        }
    """
    days = int(request.args.get("days", current_app.config["DEFAULT_LOOKAHEAD_DAYS"]))
    today = date.today()
    end_date = today + timedelta(days=days)

    status_filters = request.args.getlist("status", type=int)

    db = get_db(current_app.config["DATABASE_PATH"])

    query = """
        SELECT * FROM events
        WHERE (first_date >= ? OR last_date >= ?)
          AND first_date <= ?
    """
    params: list = [str(today), str(today), str(end_date)]

    if status_filters:
        placeholders = ",".join("?" * len(status_filters))
        query += f" AND event_status IN ({placeholders})"
        params.extend(status_filters)

    query += " ORDER BY venue_name ASC, first_date ASC"

    rows = db.execute(query, params).fetchall()

    # Group by venue
    grouped: dict = {}
    for row in rows:
        event = _add_status_label(_row_to_dict(row))
        key = event.get("venue_id") or "no_venue"
        if key not in grouped:
            grouped[key] = {
                "venue_id": event.get("venue_id"),
                "venue_name": event.get("venue_name") or "No Venue",
                "venue_city": event.get("venue_city"),
                "venue_state": event.get("venue_state"),
                "event_count": 0,
                "events": [],
            }
        grouped[key]["events"].append(event)
        grouped[key]["event_count"] += 1

    venues = sorted(grouped.values(), key=lambda v: v["venue_name"] or "")

    return jsonify(
        venues=venues,
        total_events=sum(v["event_count"] for v in venues),
        window={"start": str(today), "end": str(end_date)},
    )


@events_bp.get("/<int:event_id>")
def get_event(event_id: int):
    """
    Return a single cached event by its Prism ID.

    Returns 404 if the event is not in the local cache.
    Use POST /api/sync/events to populate the cache first.
    """
    db = get_db(current_app.config["DATABASE_PATH"])
    row = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        return jsonify(error=f"Event {event_id} not found in local cache"), 404
    return jsonify(_add_status_label(_row_to_dict(row)))
