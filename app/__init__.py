"""Flask application factory."""
import os
from flask import Flask

from config import Config
from .database import init_db


def create_app(config_object: object = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)

    # Ensure the instance folder exists
    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)

    # Initialise SQLite schema
    with app.app_context():
        init_db(app.config["DATABASE_PATH"])

    # Register blueprints
    from .routes.events import events_bp
    from .routes.venues import venues_bp
    from .routes.stages import stages_bp
    from .routes.run_of_show import ros_bp
    from .routes.sync import sync_bp
    from .routes.ui import ui_bp

    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(venues_bp, url_prefix="/api/venues")
    app.register_blueprint(stages_bp, url_prefix="/api/stages")
    app.register_blueprint(ros_bp, url_prefix="/api/run-of-show")
    app.register_blueprint(sync_bp, url_prefix="/api/sync")
    app.register_blueprint(ui_bp)  # serves / and /settings

    @app.get("/api/health")
    def health():
        from flask import jsonify
        from .database import get_db
        db = get_db(app.config["DATABASE_PATH"])
        stats = {}
        for table in ("venues", "stages", "events", "run_of_show_items"):
            row = db.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            stats[f"{table}_count"] = row["n"]
        last_sync = db.execute(
            "SELECT MAX(synced_at) AS ts FROM events"
        ).fetchone()["ts"]
        from .sdk_bridge import _resolve_token
        return jsonify(
            status="ok",
            table_stats=stats,
            last_events_sync=last_sync,
            prism_token_set=bool(_resolve_token()),
        )

    return app
