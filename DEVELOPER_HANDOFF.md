# Developer handoff

## Product

**Kaizen Student Portal v1.0.0**

The development team has completed the application. The DevOps team is responsible for deploying it into AWS.

## Functional requirements

Users can:

1. Add a student.
2. View available courses.
3. register a student for a course.
4. View registrations.
5. Upload and download a student's résumé.

## Runtime requirements

- Python 3.10 or newer
- TCP port 8000
- MySQL-compatible database
- Private S3 bucket
- Writable temporary filesystem
- Outbound access to the RDS endpoint and AWS S3 API

## Required environment variables

Production must set:

- `SECRET_KEY`
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `STORAGE_BACKEND=s3`
- `S3_BUCKET_NAME`
- `AWS_REGION`

Optional:

- `APP_VERSION`
- `LOG_LEVEL`
- `PORT`
- `S3_PREFIX`
- `MAX_UPLOAD_MB`
- `GUNICORN_WORKERS`
- `GUNICORN_THREADS`

## Operational endpoints

### `GET /health`

Lightweight application health check. It does not query RDS or S3. Use this for the ALB target group health check.

Expected status: `200`

### `GET /ready`

Dependency readiness check. It queries the database.

Expected status:

- `200` when the database is reachable
- `503` when the database is unavailable

### `GET /version`

Returns the application name and version.

### `GET /instance`

Returns the Linux hostname that handled the request. This is useful for demonstrating load balancing.

## Database deployment

Apply schema migrations from one controlled host or deployment step:

```bash
flask --app wsgi db upgrade
```

Load starter courses:

```bash
flask --app wsgi seed-db
```

## Logging

The application writes logs to stdout and stderr. In a systemd deployment, inspect them with:

```bash
journalctl -u <service-name>
```

The DevOps team should forward logs to CloudWatch Logs.

## Not included in the developer handoff

The development team has not provided:

- VPC or subnets
- Security groups
- RDS instance
- S3 bucket
- IAM role or policy
- EC2 launch template
- Auto Scaling Group
- Application Load Balancer
- systemd unit
- User-data bootstrap script
- CloudWatch dashboard or alarms
- SNS topics
- Deployment or rollback automation

Those are the project deliverables.
