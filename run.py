"""
Application entry point.

Usage
-----
    # Activate your venv first, then:
    python run.py

Or with Flask's built-in server directly:
    flask --app run:app run --debug
"""

from dotenv import load_dotenv

load_dotenv()  # Load .env before importing app so config picks up env vars

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(
        host=app.config.get("FLASK_HOST", "127.0.0.1"),
        port=int(app.config.get("FLASK_PORT", 6161)),
        debug=app.config.get("DEBUG", False),
    )
