import pytest

from app import create_app
from app.extensions import db
from app.models import Course, Student


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_ENGINE_OPTIONS": {},
            "STORAGE_BACKEND": "local",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )

    with application.app_context():
        db.create_all()
        db.session.add(
            Student(
                first_name="Test",
                last_name="Student",
                email="test@example.com",
            )
        )
        db.session.add(
            Course(
                code="TEST-101",
                name="Test Course",
                description="Course used by automated tests.",
                capacity=2,
            )
        )
        db.session.commit()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
