"""
Stages endpoints.

GET /api/stages               - All active stages (flat list, with parent venue info)
GET /api/stages/<id>          - Single stage
GET /api/stages/<id>/run-of-show - Run-of-show items for this stage
"""

from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request

from ..database import get_db

stages_bp = Blueprint("stages", __name__)

_STATUS = {0: "HOLD", 2: "CONFIRMED", 3: "IN_SETTLEMENT", 4: "SETTLED"}


# ── Routes ─────────────────────────────────────────────────────────────────────

@stages_bp.get("")
def list_stages():
    """
    Return all stages, joined with their parent venue.

    Query parameters
    ----------------
    include_inactive : bool (default false)
        Include inactive stages.
    venue_id : int
        Restrict to stages belonging to a specific venue.

    Returns
    -------
    JSON object
        {
          "stages": [
            {
              "id": 57741,
              "name": "Steinmetz Hall",
              "active": 1,
              "capacity": 1770,
              "color": "#dec523",
              "venue_id": 54469,
              "venue_name": "Dr. Phillips Center",
              "venue_city": "Orlando",
              "venue_state": "FL",
              "venue_timezone": "America/New_York"
            },
            ...
          ],
          "total": <int>
        }
    """
    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    venue_id = request.args.get("venue_id", type=int)

    db = get_db(current_app.config["DATABASE_PATH"])

    query = """
        SELECT
            s.id, s.name, s.active, s.capacity, s.color, s.venue_id,
            v.name  AS venue_name,
            v.city  AS venue_city,
            v.state AS venue_state,
            v.timezone AS venue_timezone
        FROM stages s
        JOIN venues v ON v.id = s.venue_id
        WHERE 1=1
    """
    params: list = []

    if not include_inactive:
        query += " AND s.active = 1"
    if venue_id:
        query += " AND s.venue_id = ?"
        params.append(venue_id)

    query += " ORDER BY v.name ASC, s.name ASC"

    rows = db.execute(query, params).fetchall()
    stages = [dict(r) for r in rows]
    return jsonify(stages=stages, total=len(stages))


@stages_bp.get("/<int:stage_id>")
def get_stage(stage_id: int):
    """Return a single stage with its parent venue info."""
    db = get_db(current_app.config["DATABASE_PATH"])
    row = db.execute(
        """
        SELECT s.*, v.name AS venue_name, v.city AS venue_city,
               v.state AS venue_state, v.timezone AS venue_timezone
        FROM stages s
        JOIN venues v ON v.id = s.venue_id
        WHERE s.id = ?
        """,
        (stage_id,),
    ).fetchone()
    if row is None:
        return jsonify(error=f"Stage {stage_id} not found"), 404
    return jsonify(dict(row))


@stages_bp.get("/<int:stage_id>/run-of-show")
def stage_run_of_show(stage_id: int):
    """
    Return run-of-show items for a specific stage.

    Query parameters
    ----------------
    start_date : str (YYYY-MM-DD, default today)
    end_date   : str (YYYY-MM-DD, default today + 30 days)
    source     : str 'api' | 'local' (default: all)

    Returns 404 if the stage is not in the local cache.
    """
    db = get_db(current_app.config["DATABASE_PATH"])

    stage_row = db.execute("SELECT id, name FROM stages WHERE id = ?", (stage_id,)).fetchone()
    if stage_row is None:
        return jsonify(error=f"Stage {stage_id} not found"), 404

    today = date.today()
    days = current_app.config["DEFAULT_LOOKAHEAD_DAYS"]
    start_date = request.args.get("start_date") or str(today)
    end_date = request.args.get("end_date") or str(today + timedelta(days=days))
    source = request.args.get("source")

    query = """
        SELECT * FROM run_of_show_items
        WHERE stage_id = ?
          AND occurs_at >= ?
          AND occurs_at <= ?
    """
    params: list = [stage_id, start_date, end_date + "T23:59:59"]

    if source in ("api", "local"):
        query += " AND source = ?"
        params.append(source)

    query += " ORDER BY occurs_at ASC"
    rows = db.execute(query, params).fetchall()

    items = []
    for r in rows:
        d = dict(r)
        d.pop("event_id_norm", None)
        d.pop("stage_id_norm", None)
        d.pop("raw_json", None)
        d["event_status_label"] = _STATUS.get(d.get("event_status"), "UNKNOWN")
        items.append(d)

    return jsonify(
        stage={"id": stage_row["id"], "name": stage_row["name"]},
        items=items,
        total=len(items),
        window={"start": start_date, "end": end_date},
    )
