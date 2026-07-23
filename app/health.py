import socket
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from .extensions import db

health_bp = Blueprint("health", __name__)


def common_payload() -> dict:
    return {
        "application": current_app.config["APP_NAME"],
        "version": current_app.config["APP_VERSION"],
        "hostname": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@health_bp.get("/health")
def health():
    payload = common_payload()
    payload["status"] = "healthy"
    return jsonify(payload), 200


@health_bp.get("/ready")
def ready():
    payload = common_payload()
    try:
        db.session.execute(text("SELECT 1"))
        payload.update({"status": "ready", "database": "connected"})
        return jsonify(payload), 200
    except Exception:
        current_app.logger.exception("database_readiness_check_failed")
        db.session.rollback()
        payload.update({"status": "not_ready", "database": "unavailable"})
        return jsonify(payload), 503


@health_bp.get("/version")
def version():
    return jsonify(
        {
            "application": current_app.config["APP_NAME"],
            "version": current_app.config["APP_VERSION"],
        }
    )


@health_bp.get("/instance")
def instance():
    return jsonify(
        {
            "hostname": socket.gethostname(),
            "application": current_app.config["APP_NAME"],
            "version": current_app.config["APP_VERSION"],
        }
    )
