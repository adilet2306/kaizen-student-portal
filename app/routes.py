from sqlalchemy.exc import IntegrityError
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from .extensions import db
from .models import Course, Registration, ResumeUpload, Student
from .storage_service import (
    StorageConfigurationError,
    StorageOperationError,
    create_download_target,
    save_upload,
)

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return render_template(
        "index.html",
        student_count=db.session.scalar(
            db.select(db.func.count()).select_from(Student)
        ),
        course_count=db.session.scalar(
            db.select(db.func.count()).select_from(Course)
        ),
        registration_count=db.session.scalar(
            db.select(db.func.count()).select_from(Registration)
        ),
        storage_backend=current_app.config["STORAGE_BACKEND"],
    )


@main_bp.route("/students", methods=["GET", "POST"])
def students():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not first_name or not last_name or not email:
            flash("First name, last name, and email are required.", "error")
        else:
            student = Student(
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
            db.session.add(student)
            try:
                db.session.commit()
                current_app.logger.info(
                    "student_created student_id=%s email=%s",
                    student.id,
                    student.email,
                )
                flash("Student created.", "success")
                return redirect(url_for("main.students"))
            except IntegrityError:
                db.session.rollback()
                flash("A student with that email already exists.", "error")

    student_rows = db.session.scalars(
        db.select(Student).order_by(Student.created_at.desc())
    ).all()
    return render_template("students.html", students=student_rows)


@main_bp.get("/courses")
def courses():
    course_rows = db.session.scalars(
        db.select(Course).order_by(Course.code)
    ).all()
    return render_template("courses.html", courses=course_rows)


@main_bp.route("/registrations", methods=["GET", "POST"])
def registrations():
    if request.method == "POST":
        try:
            student_id = int(request.form.get("student_id", ""))
            course_id = int(request.form.get("course_id", ""))
        except ValueError:
            flash("Select a valid student and course.", "error")
            return redirect(url_for("main.registrations"))

        student = db.session.get(Student, student_id)
        course = db.session.get(Course, course_id)

        if not student or not course:
            flash("The selected student or course does not exist.", "error")
        elif course.seats_remaining <= 0:
            flash("The selected course is full.", "error")
        else:
            registration = Registration(
                student_id=student.id,
                course_id=course.id,
            )
            db.session.add(registration)
            try:
                db.session.commit()
                current_app.logger.info(
                    "student_registered registration_id=%s student_id=%s course_id=%s",
                    registration.id,
                    student.id,
                    course.id,
                )
                flash("Registration created.", "success")
                return redirect(url_for("main.registrations"))
            except IntegrityError:
                db.session.rollback()
                flash("This student is already registered for that course.", "error")

    students = db.session.scalars(
        db.select(Student).order_by(Student.last_name, Student.first_name)
    ).all()
    courses = db.session.scalars(
        db.select(Course).order_by(Course.code)
    ).all()
    registration_rows = db.session.scalars(
        db.select(Registration).order_by(Registration.registered_at.desc())
    ).all()

    return render_template(
        "registrations.html",
        students=students,
        courses=courses,
        registrations=registration_rows,
    )


@main_bp.route("/uploads", methods=["GET", "POST"])
def uploads():
    if request.method == "POST":
        try:
            student_id = int(request.form.get("student_id", ""))
        except ValueError:
            flash("Select a valid student.", "error")
            return redirect(url_for("main.uploads"))

        student = db.session.get(Student, student_id)
        file = request.files.get("resume")

        if not student:
            flash("The selected student does not exist.", "error")
        elif not file or not file.filename:
            flash("Choose a file to upload.", "error")
        else:
            try:
                storage_key, content_type, size_bytes = save_upload(
                    file,
                    student.id,
                )
                upload = ResumeUpload(
                    student_id=student.id,
                    original_filename=file.filename,
                    storage_key=storage_key,
                    content_type=content_type,
                    size_bytes=size_bytes,
                )
                db.session.add(upload)
                db.session.commit()
                current_app.logger.info(
                    "resume_uploaded upload_id=%s student_id=%s backend=%s key=%s",
                    upload.id,
                    student.id,
                    current_app.config["STORAGE_BACKEND"],
                    storage_key,
                )
                flash("Résumé uploaded.", "success")
                return redirect(url_for("main.uploads"))
            except (StorageConfigurationError, StorageOperationError) as error:
                db.session.rollback()
                flash(str(error), "error")

    students = db.session.scalars(
        db.select(Student).order_by(Student.last_name, Student.first_name)
    ).all()
    upload_rows = db.session.scalars(
        db.select(ResumeUpload).order_by(ResumeUpload.uploaded_at.desc())
    ).all()

    return render_template(
        "uploads.html",
        students=students,
        uploads=upload_rows,
        storage_backend=current_app.config["STORAGE_BACKEND"],
    )


@main_bp.get("/uploads/<int:upload_id>/download")
def download_upload(upload_id: int):
    upload = db.get_or_404(ResumeUpload, upload_id)

    try:
        target = create_download_target(upload.storage_key)
    except (StorageConfigurationError, StorageOperationError) as error:
        flash(str(error), "error")
        return redirect(url_for("main.uploads"))

    if target["backend"] == "s3":
        return redirect(target["url"])

    path = target["path"]
    if not path.exists():
        flash("The local file no longer exists.", "error")
        return redirect(url_for("main.uploads"))

    return send_file(
        path,
        as_attachment=True,
        download_name=upload.original_filename,
        mimetype=upload.content_type,
    )
