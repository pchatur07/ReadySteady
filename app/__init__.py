"""ReadySteady: campus canteen pre-ordering system. Application factory."""
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from . import db


def create_app(config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.update(
        SECRET_KEY=os.environ.get("READYTEADY_SECRET", "dev-only-change-me"),
        DATABASE=os.environ.get("READYTEADY_DB", str(Path(app.instance_path) / "readyteady.db")),
        EMAIL_SUFFIX=os.environ.get("READYTEADY_EMAIL_SUFFIX", ".ac.in"),
        CLOCK=datetime.now,  # injected so tests can freeze time
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)
    app.json.sort_keys = False  # keep status order as the life cycle, not alphabetical

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    conn = db.connect(app.config["DATABASE"])
    db.init_db(conn)
    conn.close()

    app.teardown_appcontext(db.close_db)

    from .api import bp
    app.register_blueprint(bp)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
