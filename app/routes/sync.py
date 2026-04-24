"""
Sync endpoints – pull fresh data from Prism into the local SQLite cache.

POST /api/sync/events         - Sync events for the next N days
POST /api/sync/venues         - Sync all active venues (+ stages)
POST /api/sync/run-of-show    - Sync run-of-show items for a date range
"""

from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request

from ..database import get_db, upsert_event, upsert_ros_item, upsert_venue
from ..sdk_bridge import SDKError, fetch_events, fetch_run_of_show, fetch_venues

sync_bp = Blueprint("sync", __name__)


# ── Routes ─────────────────────────────────────────────────────────────────────

@sync_bp.post("/events")
def sync_events():
    """
    Fetch events from Prism and store them in the local cache.

    Request body (JSON, all optional)
    ----------------------------------
    days : int (default 30)
        How many days ahead to fetch from today.
    status : list[int]
        EventStatus values to include.
        0=HOLD, 2=CONFIRMED, 3=IN_SETTLEMENT, 4=SETTLED
        Omit to fetch all statuses.
    include_archived : bool (default false)
        Include archived events.
    show_type : str
        'all' | 'rental' | 'talent'

    Returns
    -------
    JSON object
        {
          "synced": <int>,       # number of events upserted
          "window": {...},
          "errors": [...]        # non-fatal per-event errors, if any
        }
    """
    body = request.get_json(silent=True) or {}
    days = int(body.get("days", current_app.config["DEFAULT_LOOKAHEAD_DAYS"]))
    today = date.today()
    end_date = today + timedelta(days=days)

    try:
        events = fetch_events(
            start_date=str(today),
            end_date=str(end_date),
            event_status=body.get("status") or None,
            show_type=body.get("show_type"),
            include_archived=bool(body.get("include_archived", False)),
        )
    except SDKError as exc:
        return jsonify(
            error=str(exc),
            validation_errors=exc.validation_errors,
        ), 502

    db = get_db(current_app.config["DATABASE_PATH"])
    errors = []
    for event in events:
        try:
            upsert_event(db, event)
        except Exception as exc:  # noqa: BLE001
            errors.append({"event_id": event.get("id"), "error": str(exc)})

    db.commit()

    return jsonify(
        synced=len(events) - len(errors),
        window={"start": str(today), "end": str(end_date)},
        errors=errors,
    )


@sync_bp.post("/venues")
def sync_venues():
    """
    Fetch venues from Prism and store them in the local cache.

    Request body (JSON, all optional)
    ----------------------------------
    include_inactive : bool (default false)
        Also sync inactive venues.

    Returns
    -------
    JSON object
        { "synced": <int>, "errors": [...] }
    """
    body = request.get_json(silent=True) or {}
    include_inactive = bool(body.get("include_inactive", False))

    try:
        venues = fetch_venues(include_inactive=include_inactive)
    except SDKError as exc:
        return jsonify(error=str(exc), validation_errors=exc.validation_errors), 502

    db = get_db(current_app.config["DATABASE_PATH"])
    errors = []
    for venue in venues:
        try:
            upsert_venue(db, venue)
        except Exception as exc:  # noqa: BLE001
            errors.append({"venue_id": venue.get("id"), "error": str(exc)})

    db.commit()

    return jsonify(synced=len(venues) - len(errors), errors=errors)


@sync_bp.post("/run-of-show")
def sync_run_of_show():
    """
    Fetch run-of-show items from Prism and store them in the local cache.

    Existing API-sourced items in the requested date window are **replaced**
    on conflict (same event/title/occurs_at/stage combination).  Locally-
    created items are never overwritten by a sync.

    Request body (JSON)
    -------------------
    start_date : str (YYYY-MM-DD) [required]
    end_date   : str (YYYY-MM-DD) [required]
    venue_ids  : list[int] (optional)  Filter to specific venues.
    stage_ids  : list[int] (optional)  Filter to specific stages.

    Returns
    -------
    JSON object
        { "synced": <int>, "skipped_duplicates": <int>, "errors": [...] }
    """
    body = request.get_json(silent=True) or {}

    start_date = body.get("start_date")
    end_date = body.get("end_date")
    if not start_date or not end_date:
        return jsonify(error="start_date and end_date are required"), 400

    try:
        items = fetch_run_of_show(
            start_date=start_date,
            end_date=end_date,
            stage_ids=body.get("stage_ids") or None,
            venue_ids=body.get("venue_ids") or None,
        )
    except SDKError as exc:
        return jsonify(error=str(exc), validation_errors=exc.validation_errors), 502

    db = get_db(current_app.config["DATABASE_PATH"])

    # Remove stale API items in this window before re-inserting so that
    # deleted Prism items don't linger in the local cache.
    db.execute(
        """
        DELETE FROM run_of_show_items
        WHERE source = 'api'
          AND occurs_at >= ?
          AND occurs_at <= ?
        """,
        (start_date, end_date + "T23:59:59"),
    )

    synced = 0
    skipped = 0
    errors = []
    for item in items:
        item["source"] = "api"
        try:
            result = upsert_ros_item(db, item)
            if result is None:
                skipped += 1
            else:
                synced += 1
        except Exception as exc:  # noqa: BLE001
            errors.append({"item_id": item.get("id"), "error": str(exc)})

    db.commit()

    return jsonify(
        synced=synced,
        skipped_duplicates=skipped,
        window={"start": start_date, "end": end_date},
        errors=errors,
    )
