"""
Application configuration loaded from environment variables.
Copy .env.example to .env and fill in your values before running.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # ── Prism API ──────────────────────────────────────────────────────────────
    PRISM_TOKEN: str = os.environ.get("PRISM_TOKEN", "")

    # ── Node.js bridge ────────────────────────────────────────────────────────
    # Directory that contains the get_events.js / get_venues.js scripts
    NODE_SCRIPTS_DIR: str = os.environ.get(
        "NODE_SCRIPTS_DIR", str(BASE_DIR / "node_scripts")
    )
    # Timeout (seconds) for a single Node.js subprocess call
    NODE_TIMEOUT: int = int(os.environ.get("NODE_TIMEOUT", "300"))

    # ── SQLite database ───────────────────────────────────────────────────────
    DATABASE_PATH: str = os.environ.get(
        "DATABASE_PATH", str(BASE_DIR / "instance" / "prism.db")
    )

    # ── Flask ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "0") == "1"

    # ── Cache / sync policy ───────────────────────────────────────────────────
    # How many days ahead to look for events by default
    DEFAULT_LOOKAHEAD_DAYS: int = int(os.environ.get("DEFAULT_LOOKAHEAD_DAYS", "30"))
    # Minutes before cached data is considered stale (0 = always fresh from DB)
    CACHE_STALE_MINUTES: int = int(os.environ.get("CACHE_STALE_MINUTES", "60"))
