"""
Browser-facing UI routes.

GET  /              - Dashboard (stats + quick sync buttons)
GET  /settings      - Settings page (token, config)
POST /settings/token        - Save a new token
POST /settings/token/clear  - Remove the stored token
POST /sync-ui/venues        - Sync venues (form submit from dashboard)
POST /sync-ui/events        - Sync events (form submit from dashboard)
POST /sync-ui/run-of-show   - Sync run of show (form submit from dashboard)
"""

from datetime import date, timedelta

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..database import get_db, get_setting, set_setting
from ..sdk_bridge import SDKError, fetch_events, fetch_run_of_show, fetch_venues
from ..database import upsert_event, upsert_ros_item, upsert_venue
from config import Config

ui_bp = Blueprint("ui", __name__)

# ── Template context helper ───────────────────────────────────────────────────

def _token_context():
    """Return template variables related to the current token status."""
    db = get_db(current_app.config["DATABASE_PATH"])
    db_token = get_setting(db, "prism_token")
    env_token = Config.PRISM_TOKEN

    if db_token:
        active = db_token
        source = "db"
    elif env_token:
        active = env_token
        source = "env"
    else:
        active = ""
        source = "none"

    masked = _mask(active) if active else None
    return dict(token_set=bool(active), current_token_masked=masked, token_source=source)


def _mask(token: str) -> str:
    """Return a masked representation keeping the last 6 characters visible."""
    if len(token) <= 6:
        return "••••••"
    return "••••••••" + token[-6:]


# ── Dashboard ─────────────────────────────────────────────────────────────────

@ui_bp.get("/")
def index():
    db = get_db(current_app.config["DATABASE_PATH"])

    stats = {}
    for table in ("venues", "stages", "events", "run_of_show_items"):
        row = db.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        stats[f"{table}_count"] = row["n"]
    stats["active_stages_count"] = db.execute(
        "SELECT COUNT(*) AS n FROM stages WHERE active = 1"
    ).fetchone()["n"]

    last_sync = db.execute("SELECT MAX(synced_at) AS ts FROM events").fetchone()["ts"]

    endpoints = [
        ("GET",    "/api/health",                         "Health check & table stats"),
        ("POST",   "/api/sync/venues",                    "Sync venues + stages from Prism"),
        ("POST",   "/api/sync/events",                    "Sync events from Prism"),
        ("POST",   "/api/sync/run-of-show",               "Sync run of show from Prism"),
        ("GET",    "/api/stages",                         "List all stages (child venues)"),
        ("GET",    "/api/stages/<id>",                    "Single stage"),
        ("GET",    "/api/stages/<id>/run-of-show",        "Run-of-show items for a stage"),
        ("GET",    "/api/venues",                         "List parent venues"),
        ("GET",    "/api/venues/<id>",                    "Single venue with stages"),
        ("GET",    "/api/venues/<id>/events",             "Upcoming events at a venue"),
        ("GET",    "/api/events",                         "Upcoming events (next 30 days)"),
        ("GET",    "/api/events/by-stage",                "Events grouped by stage"),
        ("GET",    "/api/events/by-venue",                "Events grouped by parent venue"),
        ("GET",    "/api/events/<id>",                    "Single event by Prism ID"),
        ("GET",    "/api/run-of-show",                    "Run-of-show items"),
        ("POST",   "/api/run-of-show/items",              "Add local run-of-show item"),
        ("DELETE", "/api/run-of-show/items/<id>",         "Delete a local item"),
    ]

    return render_template(
        "index.html",
        stats=stats,
        last_sync=last_sync,
        endpoints=endpoints,
        **_token_context(),
    )


# ── Events list ───────────────────────────────────────────────────────────────

@ui_bp.get("/events")
def events_list():
    db = get_db(current_app.config["DATABASE_PATH"])
    today = date.today()
    end = today + timedelta(days=30)

    _STATUS = {0: "HOLD", 2: "CONFIRMED", 3: "IN_SETTLEMENT", 4: "SETTLED"}
    _STATUS_COLOR = {
        0: "#f59e0b",
        2: "#059669",
        3: "#2563eb",
        4: "#64748b",
    }

    rows = db.execute(
        """
        SELECT * FROM events
        WHERE (first_date >= ? OR last_date >= ?)
          AND first_date <= ?
        ORDER BY first_date ASC, name ASC
        """,
        (str(today), str(today), str(end)),
    ).fetchall()

    events = []
    for row in rows:
        e = dict(row)
        e.pop("raw_json", None)
        status = e.get("event_status")
        e["status_label"] = _STATUS.get(status, "UNKNOWN")
        e["status_color"] = _STATUS_COLOR.get(status, "#94a3b8")
        events.append(e)

    return render_template(
        "events_list.html",
        events=events,
        window_start=str(today),
        window_end=str(end),
        **_token_context(),
    )


# ── Settings ──────────────────────────────────────────────────────────────────

@ui_bp.get("/settings")
def settings():
    config_rows = [
        ("DATABASE_PATH",          current_app.config["DATABASE_PATH"]),
        ("NODE_SCRIPTS_DIR",       current_app.config["NODE_SCRIPTS_DIR"]),
        ("NODE_TIMEOUT",           f"{current_app.config['NODE_TIMEOUT']}s"),
        ("DEFAULT_LOOKAHEAD_DAYS", str(current_app.config["DEFAULT_LOOKAHEAD_DAYS"])),
    ]
    return render_template("settings.html", config_rows=config_rows, **_token_context())


@ui_bp.post("/settings/token")
def save_token():
    token = (request.form.get("token") or "").strip()
    if not token:
        flash("Token cannot be empty.", "error")
        return redirect(url_for("ui.settings"))

    db = get_db(current_app.config["DATABASE_PATH"])
    set_setting(db, "prism_token", token)
    db.commit()
    flash("Token saved successfully.", "success")
    return redirect(url_for("ui.settings"))


@ui_bp.post("/settings/token/clear")
def clear_token():
    db = get_db(current_app.config["DATABASE_PATH"])
    set_setting(db, "prism_token", "")
    db.commit()
    flash("Token cleared. API calls will now fall back to the PRISM_TOKEN environment variable.", "info")
    return redirect(url_for("ui.settings"))


# ── Dashboard sync form handlers ──────────────────────────────────────────────

@ui_bp.post("/sync-ui/venues")
def sync_venues_ui():
    try:
        venues = fetch_venues()
        db = get_db(current_app.config["DATABASE_PATH"])
        for v in venues:
            upsert_venue(db, v)
        db.commit()
        flash(f"Synced {len(venues)} venues.", "success")
    except SDKError as exc:
        flash(f"Sync failed: {exc}", "error")
    return redirect(url_for("ui.index"))


@ui_bp.post("/sync-ui/events")
def sync_events_ui():
    days = int(request.form.get("days", 30))
    today = date.today()
    end = today + timedelta(days=days)
    try:
        events = fetch_events(start_date=str(today), end_date=str(end))
        db = get_db(current_app.config["DATABASE_PATH"])
        for e in events:
            upsert_event(db, e)
        db.commit()
        flash(f"Synced {len(events)} events ({today} → {end}).", "success")
    except SDKError as exc:
        flash(f"Sync failed: {exc}", "error")
    return redirect(url_for("ui.index"))


@ui_bp.post("/sync-ui/run-of-show")
def sync_ros_ui():
    today = date.today()
    end = today + timedelta(days=30)
    try:
        items = fetch_run_of_show(start_date=str(today), end_date=str(end))
        db = get_db(current_app.config["DATABASE_PATH"])
        db.execute(
            "DELETE FROM run_of_show_items WHERE source='api' AND occurs_at >= ? AND occurs_at <= ?",
            (str(today), str(end) + "T23:59:59"),
        )
        count = 0
        for item in items:
            item["source"] = "api"
            if upsert_ros_item(db, item) is not None:
                count += 1
        db.commit()
        flash(f"Synced {count} run-of-show items ({today} → {end}).", "success")
    except SDKError as exc:
        flash(f"Sync failed: {exc}", "error")
    return redirect(url_for("ui.index"))
