"""
Run-of-show endpoints.

GET    /api/run-of-show              - Query items from cache
GET    /api/run-of-show/<id>         - Single item by local DB id
POST   /api/run-of-show/items        - Add a local run-of-show item (duplicate-safe)
DELETE /api/run-of-show/items/<id>   - Delete a locally-created item
"""

from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request

from ..database import get_db, upsert_ros_item

ros_bp = Blueprint("run_of_show", __name__)

_STATUS = {0: "HOLD", 2: "CONFIRMED", 3: "IN_SETTLEMENT", 4: "SETTLED"}


def _row_to_dict(row) -> dict:
    d = dict(row)
    # Strip computed/internal columns the caller never needs
    d.pop("event_id_norm", None)
    d.pop("stage_id_norm", None)
    d.pop("raw_json", None)
    d["event_status_label"] = _STATUS.get(d.get("event_status"), "UNKNOWN")
    return d


# ── Routes ─────────────────────────────────────────────────────────────────────

@ros_bp.get("")
def list_items():
    """
    Return run-of-show items from the local cache.

    Query parameters
    ----------------
    start_date : str (YYYY-MM-DD, default today)
        Only return items that occur on or after this date.
    end_date : str (YYYY-MM-DD, default today + 30 days)
        Only return items that occur on or before this date.
    venue_id : int
        Filter to a specific venue.
    stage_id : int
        Filter to a specific stage.
    event_id : int
        Filter to a specific event.
    source : str ('api' | 'local')
        Return only items from one source.

    Returns
    -------
    JSON object
        {
          "items": [...],
          "total": <int>,
          "window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        }
    """
    today = date.today()
    days = current_app.config["DEFAULT_LOOKAHEAD_DAYS"]
    start_date = request.args.get("start_date") or str(today)
    end_date = request.args.get("end_date") or str(today + timedelta(days=days))

    venue_id = request.args.get("venue_id", type=int)
    stage_id = request.args.get("stage_id", type=int)
    event_id = request.args.get("event_id", type=int)
    source = request.args.get("source")

    db = get_db(current_app.config["DATABASE_PATH"])

    query = """
        SELECT * FROM run_of_show_items
        WHERE occurs_at >= ?
          AND occurs_at <= ?
    """
    params: list = [start_date, end_date + "T23:59:59"]

    if venue_id:
        query += " AND venue_id = ?"
        params.append(venue_id)
    if stage_id:
        query += " AND stage_id = ?"
        params.append(stage_id)
    if event_id:
        query += " AND event_id = ?"
        params.append(event_id)
    if source in ("api", "local"):
        query += " AND source = ?"
        params.append(source)

    query += " ORDER BY occurs_at ASC"

    rows = db.execute(query, params).fetchall()
    items = [_row_to_dict(r) for r in rows]

    return jsonify(items=items, total=len(items), window={"start": start_date, "end": end_date})


@ros_bp.get("/<int:item_id>")
def get_item(item_id: int):
    """Return a single run-of-show item by its local database id."""
    db = get_db(current_app.config["DATABASE_PATH"])
    row = db.execute(
        "SELECT * FROM run_of_show_items WHERE id = ?", (item_id,)
    ).fetchone()
    if row is None:
        return jsonify(error=f"Run-of-show item {item_id} not found"), 404
    return jsonify(_row_to_dict(row))


@ros_bp.post("/items")
def create_item():
    """
    Add a new run-of-show item to the local database.

    This endpoint writes **local** items (``source = 'local'``).  The
    Prism API does not currently expose a write endpoint for run-of-show
    items, so data written here is stored only in the local SQLite cache.

    Duplicate detection
    -------------------
    An item is considered a duplicate when the combination of
    ``event_id``, ``title``, ``occurs_at``, and ``stage_id`` already
    exists in the database.  A 409 response is returned with the
    conflicting item's id so the caller can retrieve or update it.

    Request body (JSON)
    -------------------
    title           : str   [required]  Display name for this item.
    occurs_at       : str   [required]  ISO datetime when the item starts
                                        (e.g. "2025-06-15T20:00:00").
    event_id        : int   [required]  Prism event this item belongs to.
    finishes_at     : str   [optional]  ISO datetime when the item ends.
    venue_id        : int   [optional]  Venue where this item takes place.
    stage_id        : int   [optional]  Stage where this item takes place.
    event_name      : str   [optional]  Human-readable event name.
    venue_name      : str   [optional]  Human-readable venue name.
    stage_name      : str   [optional]  Human-readable stage name.
    event_description: str  [optional]  Free-text description.

    Returns
    -------
    201  – Item created successfully; body contains the new item.
    400  – Missing required fields or malformed JSON.
    409  – Duplicate detected; body contains the existing item's id.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    # Validate required fields
    missing = [f for f in ("title", "occurs_at", "event_id") if not data.get(f)]
    if missing:
        return jsonify(
            error="Missing required fields",
            missing_fields=missing,
        ), 400

    # Normalise occurs_at: accept plain dates as midnight ISO datetime
    occurs_at: str = str(data["occurs_at"]).strip()
    if len(occurs_at) == 10:  # YYYY-MM-DD only
        occurs_at += "T00:00:00"

    item = {
        "title": str(data["title"]).strip(),
        "occurs_at": occurs_at,
        "finishes_at": data.get("finishes_at"),
        "event": {
            "id": int(data["event_id"]),
            "name": data.get("event_name", ""),
        },
        "venue": {
            "id": data.get("venue_id"),
            "name": data.get("venue_name", ""),
        } if data.get("venue_id") else None,
        "stage": {
            "id": data.get("stage_id"),
            "name": data.get("stage_name", ""),
        } if data.get("stage_id") else None,
        "event_description": data.get("event_description"),
        "source": "local",
    }

    db = get_db(current_app.config["DATABASE_PATH"])
    new_id = upsert_ros_item(db, item)

    if new_id is None:
        # Duplicate – find the conflicting row
        event_id = int(data["event_id"])
        stage_id = data.get("stage_id")
        dup_query = """
            SELECT id FROM run_of_show_items
            WHERE event_id_norm = COALESCE(?, -1)
              AND title = ?
              AND occurs_at = ?
              AND stage_id_norm = COALESCE(?, -1)
            LIMIT 1
        """
        dup_row = db.execute(
            dup_query, (event_id, item["title"], occurs_at, stage_id)
        ).fetchone()
        existing_id = dup_row["id"] if dup_row else None
        return jsonify(
            error="Duplicate run-of-show item",
            detail=(
                f"An item with the same event_id, title, occurs_at, and stage_id "
                f"already exists (id={existing_id})."
            ),
            existing_id=existing_id,
        ), 409

    db.commit()
    created_row = db.execute(
        "SELECT * FROM run_of_show_items WHERE id = ?", (new_id,)
    ).fetchone()
    return jsonify(_row_to_dict(created_row)), 201


@ros_bp.delete("/items/<int:item_id>")
def delete_item(item_id: int):
    """
    Delete a locally-created run-of-show item.

    Only items with ``source = 'local'`` may be deleted this way.
    API-sourced items are managed by syncing from Prism; to remove an
    API item from the local cache re-sync the relevant date range.

    Returns 404 if the item does not exist, 403 if it is API-sourced.
    """
    db = get_db(current_app.config["DATABASE_PATH"])
    row = db.execute(
        "SELECT id, source FROM run_of_show_items WHERE id = ?", (item_id,)
    ).fetchone()

    if row is None:
        return jsonify(error=f"Run-of-show item {item_id} not found"), 404

    if row["source"] != "local":
        return jsonify(
            error="Cannot delete API-sourced items via this endpoint",
            detail="Re-sync the date range to refresh API items.",
        ), 403

    db.execute("DELETE FROM run_of_show_items WHERE id = ?", (item_id,))
    db.commit()
    return jsonify(deleted=True, id=item_id)
