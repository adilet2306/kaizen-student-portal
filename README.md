# Kaizen Student Portal

A small Flask application prepared as a **developer handoff** for a DevOps deployment project.

The application provides:

- Student creation
- Course catalog
- Course registration
- Résumé upload using local storage or Amazon S3
- MySQL support for Amazon RDS
- SQLite fallback for local development
- Database migrations
- Health, readiness, version, and instance endpoints
- Gunicorn production entry point
- Basic automated tests

## Application contract

| Item | Value |
|---|---|
| Language | Python 3.10+ |
| Framework | Flask |
| Production server | Gunicorn |
| Default port | `8000` |
| Database | MySQL on Amazon RDS |
| Object storage | Amazon S3 |
| Load balancer health path | `/health` |
| Dependency readiness path | `/ready` |
| Version endpoint | `/version` |
| Instance endpoint | `/instance` |

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
flask --app wsgi db upgrade
flask --app wsgi seed-db

gunicorn -c gunicorn.conf.py wsgi:app
```

Open:

```text
http://localhost:8000
```

Verify:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
curl -s http://localhost:8000/version
curl -s http://localhost:8000/instance
```

## Run tests

```bash
pytest -q
```

## Amazon RDS configuration

Configure these environment variables:

```bash
DB_HOST=your-rds-endpoint
DB_PORT=3306
DB_NAME=student_portal
DB_USER=portal_app
DB_PASSWORD=your-password
```

Alternatively, set one URL:

```bash
DATABASE_URL='mysql+pymysql://portal_app:password@rds-endpoint:3306/student_portal'
```

Run migrations once from a controlled deployment step:

```bash
flask --app wsgi db upgrade
flask --app wsgi seed-db
```

Do not run `seed-db` from every Auto Scaling instance. It is idempotent, but database changes should still be controlled.

## Amazon S3 configuration

Configure:

```bash
STORAGE_BACKEND=s3
S3_BUCKET_NAME=your-private-bucket
AWS_REGION=us-east-1
S3_PREFIX=resumes
```

The application intentionally does not accept static AWS access keys. On EC2, attach an IAM role that permits the required S3 operations.

Minimum application operations:

- `s3:PutObject`
- `s3:GetObject`

The bucket should remain private. Downloads use short-lived presigned URLs.

## Production command

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

Students should create the final Linux user, directory layout, environment file, systemd service, EC2 user data, load balancer, Auto Scaling Group, RDS, S3, IAM, CloudWatch, and SNS configuration.

See [DEVELOPER_HANDOFF.md](DEVELOPER_HANDOFF.md).
