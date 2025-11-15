from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, request

from .config.settings import AppConfig
from .api.routes import api_blueprint
from .api.documents import documents_blueprint, documents_pages_blueprint
from .api.findings import findings_blueprint
from .api.audits import audits_blueprint, audits_pages_blueprint
from .api.scores import scores_blueprint
from .api.review import review_blueprint
from .db.models import Base
from .db.session import init_engine, shutdown_session
from .logging_config import configure_logging

load_dotenv()


def create_app(config_class: type[AppConfig] | None = None) -> Flask:
    """Application factory used by Flask and CLI utilities."""
    config = config_class() if config_class else AppConfig()

    # Configure logging
    json_output = os.getenv("LOG_JSON", "1") == "1"
    configure_logging(log_level=config.log_level, json_output=json_output)

    # Initialize Flask app with templates folder
    template_dir = Path(__file__).parent / "templates"
    app = Flask(__name__, template_folder=str(template_dir))
    app.config.from_mapping(config.to_flask_dict())

    register_blueprints(app)
    register_middleware(app)
    ensure_storage_roots(config)
    init_database(app, config)

    return app


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(api_blueprint)
    app.register_blueprint(documents_blueprint)
    app.register_blueprint(documents_pages_blueprint)
    app.register_blueprint(findings_blueprint)
    app.register_blueprint(audits_blueprint)
    app.register_blueprint(audits_pages_blueprint)
    app.register_blueprint(scores_blueprint)
    app.register_blueprint(review_blueprint)


def register_middleware(app: Flask) -> None:
    """Register Flask middleware for request ID tracking."""
    from .logging_config import clear_context, set_request_id
    import uuid

    @app.before_request
    def set_request_context():
        """Set request ID for logging correlation."""
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        g.request_id = request_id

    @app.after_request
    def add_request_id_header(response):
        """Add request ID to response headers."""
        if hasattr(g, "request_id"):
            response.headers["X-Request-ID"] = g.request_id
        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID"
        return response
    
    @app.before_request
    def handle_preflight():
        """Handle CORS preflight requests."""
        if request.method == "OPTIONS":
            response = app.make_default_options_response()
            headers = response.headers
            headers["Access-Control-Allow-Origin"] = "*"
            headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID"
            return response

    @app.teardown_request
    def clear_logging_context(_):
        """Clear logging context after request."""
        clear_context()


def ensure_storage_roots(config: AppConfig) -> None:
    Path(config.data_root).mkdir(parents=True, exist_ok=True)
    for folder_name in ("uploads", "processed", "logs", "chroma"):
        Path(config.data_root, folder_name).mkdir(parents=True, exist_ok=True)


def init_database(app: Flask, config: AppConfig) -> None:
    if config.database_url.startswith("sqlite:///"):
        sqlite_path = config.sqlite_path
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    engine = init_engine(config.database_url)
    Base.metadata.create_all(engine)
    app.teardown_appcontext(shutdown_session)


app = create_app()

