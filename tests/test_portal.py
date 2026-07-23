from app.extensions import db
from app.models import Registration, Student


def test_create_student(client, app):
    response = client.post(
        "/students",
        data={
            "first_name": "New",
            "last_name": "Learner",
            "email": "new.learner@example.com",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Student created" in response.data

    with app.app_context():
        created = db.session.scalar(
            db.select(Student).where(
                Student.email == "new.learner@example.com"
            )
        )
        assert created is not None


def test_register_student(client, app):
    with app.app_context():
        student = db.session.scalar(db.select(Student))
        from app.models import Course
        course = db.session.scalar(db.select(Course))
        student_id = student.id
        course_id = course.id

    response = client.post(
        "/registrations",
        data={"student_id": student_id, "course_id": course_id},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Registration created" in response.data

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(Registration)
        ) == 1
