"""
Venues endpoints.

GET /api/venues           - All cached venues
GET /api/venues/<id>      - Single venue with stages
GET /api/venues/<id>/events - Upcoming events at a venue
"""

from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request

from ..database import get_db

venues_bp = Blueprint("venues", __name__)


def _row_to_dict(row) -> dict:
    return dict(row)


# ── Routes ─────────────────────────────────────────────────────────────────────

@venues_bp.get("")
def list_venues():
    """
    Return all venues stored in the local cache.

    Query parameters
    ----------------
    include_inactive : bool (default false)
        Pass ``include_inactive=true`` to include inactive venues.

    Returns
    -------
    JSON object
        {
          "venues": [...],
          "total": <int>
        }
    """
    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    db = get_db(current_app.config["DATABASE_PATH"])

    query = "SELECT * FROM venues"
    if not include_inactive:
        query += " WHERE active = 1"
    query += " ORDER BY name ASC"

    rows = db.execute(query).fetchall()
    venues = []
    for row in rows:
        v = _row_to_dict(row)
        # Attach stages from the stages sub-table
        stage_rows = db.execute(
            "SELECT * FROM stages WHERE venue_id = ? ORDER BY name ASC", (v["id"],)
        ).fetchall()
        v["stages"] = [_row_to_dict(s) for s in stage_rows]
        # Remove the redundant JSON blob from the list view
        v.pop("raw_json", None)
        v.pop("stages_json", None)
        venues.append(v)

    return jsonify(venues=venues, total=len(venues))


@venues_bp.get("/<int:venue_id>")
def get_venue(venue_id: int):
    """
    Return a single venue with its stages.

    Returns 404 if the venue is not in the local cache.
    """
    db = get_db(current_app.config["DATABASE_PATH"])
    row = db.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
    if row is None:
        return jsonify(error=f"Venue {venue_id} not found in local cache"), 404

    venue = _row_to_dict(row)
    stage_rows = db.execute(
        "SELECT * FROM stages WHERE venue_id = ? ORDER BY name ASC", (venue_id,)
    ).fetchall()
    venue["stages"] = [_row_to_dict(s) for s in stage_rows]
    venue.pop("raw_json", None)
    venue.pop("stages_json", None)
    return jsonify(venue)


@venues_bp.get("/<int:venue_id>/events")
def venue_events(venue_id: int):
    """
    Return upcoming events at a specific venue.

    Query parameters
    ----------------
    days : int (default 30)
        How many days ahead to look.
    status : int
        Filter to a specific EventStatus value. May be repeated.

    Returns 404 if the venue is not in the local cache.
    """
    db = get_db(current_app.config["DATABASE_PATH"])

    # Verify venue exists
    venue_row = db.execute("SELECT id, name FROM venues WHERE id = ?", (venue_id,)).fetchone()
    if venue_row is None:
        return jsonify(error=f"Venue {venue_id} not found in local cache"), 404

    days = int(request.args.get("days", current_app.config["DEFAULT_LOOKAHEAD_DAYS"]))
    today = date.today()
    end_date = today + timedelta(days=days)

    status_filters = request.args.getlist("status", type=int)

    query = """
        SELECT * FROM events
        WHERE venue_id = ?
          AND (first_date >= ? OR last_date >= ?)
          AND first_date <= ?
    """
    params: list = [venue_id, str(today), str(today), str(end_date)]

    if status_filters:
        placeholders = ",".join("?" * len(status_filters))
        query += f" AND event_status IN ({placeholders})"
        params.extend(status_filters)

    query += " ORDER BY first_date ASC"
    rows = db.execute(query, params).fetchall()

    _STATUS = {0: "HOLD", 2: "CONFIRMED", 3: "IN_SETTLEMENT", 4: "SETTLED"}
    events = []
    for row in rows:
        e = dict(row)
        e["status_label"] = _STATUS.get(e.get("event_status"), "UNKNOWN")
        events.append(e)

    return jsonify(
        venue={"id": venue_row["id"], "name": venue_row["name"]},
        events=events,
        total=len(events),
        window={"start": str(today), "end": str(end_date)},
    )
