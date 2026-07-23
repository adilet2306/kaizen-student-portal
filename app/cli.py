import click
from flask import Flask

from .extensions import db
from .models import Course, Student


COURSES = [
    {
        "code": "DEVOPS-101",
        "name": "DevOps Foundations",
        "description": "Linux, Git, networking, and delivery fundamentals.",
        "capacity": 24,
    },
    {
        "code": "AWS-201",
        "name": "AWS Infrastructure",
        "description": "VPC, EC2, load balancing, Auto Scaling, RDS, and S3.",
        "capacity": 20,
    },
    {
        "code": "MON-220",
        "name": "Cloud Monitoring",
        "description": "CloudWatch metrics, logs, dashboards, alarms, and SNS.",
        "capacity": 18,
    },
]


def register_commands(app: Flask) -> None:
    @app.cli.command("seed-db")
    def seed_db():
        for item in COURSES:
            existing = db.session.scalar(
                db.select(Course).where(Course.code == item["code"])
            )
            if existing is None:
                db.session.add(Course(**item))

        demo_student = db.session.scalar(
            db.select(Student).where(Student.email == "demo@kaizen.local")
        )
        if demo_student is None:
            db.session.add(
                Student(
                    first_name="Demo",
                    last_name="Student",
                    email="demo@kaizen.local",
                )
            )

        db.session.commit()
        click.echo("Seed data is ready.")
