import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def build_database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL", "").strip()
    if explicit_url:
        if explicit_url.startswith("mysql://"):
            return explicit_url.replace("mysql://", "mysql+pymysql://", 1)
        return explicit_url

    db_host = os.getenv("DB_HOST", "").strip()
    if not db_host:
        return f"sqlite:///{PROJECT_ROOT / 'instance' / 'student_portal.db'}"

    user = quote_plus(os.getenv("DB_USER", "portal_app"))
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    host = db_host
    port = os.getenv("DB_PORT", "3306")
    database = os.getenv("DB_NAME", "student_portal")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


class Config:
    APP_NAME = os.getenv("APP_NAME", "Kaizen Student Portal")
    APP_VERSION = os.getenv(
        "APP_VERSION",
        (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip(),
    )
    APP_ENV = os.getenv("APP_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-secret")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    PORT = int(os.getenv("PORT", "8000"))

    SQLALCHEMY_DATABASE_URI = build_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    S3_PREFIX = os.getenv("S3_PREFIX", "resumes").strip("/")

    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "5"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    UPLOAD_FOLDER = str(PROJECT_ROOT / "instance" / "uploads")
    ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "doc", "docx", "txt"}
