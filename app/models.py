from datetime import datetime, timezone

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    registrations = db.relationship(
        "Registration",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    uploads = db.relationship(
        "ResumeUpload",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    capacity = db.Column(db.Integer, nullable=False, default=20)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    registrations = db.relationship(
        "Registration",
        back_populates="course",
        cascade="all, delete-orphan",
    )

    @property
    def seats_remaining(self) -> int:
        return max(self.capacity - len(self.registrations), 0)


class Registration(db.Model):
    __tablename__ = "registrations"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "course_id",
            name="uq_registration_student_course",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id = db.Column(
        db.Integer,
        db.ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    registered_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    student = db.relationship("Student", back_populates="registrations")
    course = db.relationship("Course", back_populates="registrations")


class ResumeUpload(db.Model):
    __tablename__ = "resume_uploads"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    storage_key = db.Column(db.String(512), nullable=False, unique=True)
    content_type = db.Column(db.String(255), nullable=False, default="application/octet-stream")
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    student = db.relationship("Student", back_populates="uploads")
