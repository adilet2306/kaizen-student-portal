import logging
import os
import sys

from flask import Flask, render_template

from .config import Config
from .extensions import db, migrate


def configure_logging(app: Flask) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s logger=%(name)s message=%(message)s"
        )
    )

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(app.config["LOG_LEVEL"])

    logging.getLogger("werkzeug").setLevel(app.config["LOG_LEVEL"])


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)

    from .health import health_bp
    from .routes import main_bp
    from .cli import register_commands

    app.register_blueprint(main_bp)
    app.register_blueprint(health_bp)
    register_commands(app)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def file_too_large(_error):
        return (
            render_template(
                "error.html",
                title="File too large",
                message=f"Maximum upload size is {app.config['MAX_UPLOAD_MB']} MB.",
            ),
            413,
        )

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.exception("unhandled_application_error", exc_info=error)
        return (
            render_template(
                "error.html",
                title="Application error",
                message="The application encountered an unexpected error.",
            ),
            500,
        )

    app.logger.info(
        "application_started app=%s version=%s environment=%s",
        app.config["APP_NAME"],
        app.config["APP_VERSION"],
        app.config["APP_ENV"],
    )

    return app
