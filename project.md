# Kaizen Student Portal on AWS
## End-to-End DevOps Deployment Lab

This guide walks students through deploying the **Kaizen Student Portal** from a single EC2 instance to a highly available AWS architecture using:

- Amazon VPC
- Public and private subnets
- Internet Gateway and route tables
- Amazon EC2
- IAM roles and policies
- Amazon RDS for MySQL
- Amazon S3
- AWS Secrets Manager
- systemd and Gunicorn
- EC2 user data
- Launch Templates
- Application Load Balancer
- Target Groups
- Auto Scaling Groups
- CloudWatch alarms
- Amazon SNS notifications

The lab intentionally starts with a manually configured EC2 instance. Students first prove that the application works, then automate and scale it.

---

# 1. Final Architecture

```text
                              Internet
                                 |
                                 v
                      Application Load Balancer
                     Public Subnet A + Subnet B
                                 |
                            HTTP :8000
                                 |
                   +-------------+-------------+
                   |                           |
                   v                           v
             EC2 Instance A              EC2 Instance B
            Flask + Gunicorn            Flask + Gunicorn
                   |                           |
                   +-------------+-------------+
                                 |
                    +------------+------------+
                    |                         |
                    v                         v
              Amazon RDS                 Amazon S3
                 MySQL                Résumé uploads
             Private subnets            Private bucket

Supporting services:
- Launch Template
- Auto Scaling Group
- Secrets Manager
- IAM role
- CloudWatch alarms
- SNS email notifications
```

---

# 2. Learning Objectives

By the end of this lab, students should be able to:

1. Run a Flask application manually on EC2.
2. Connect an EC2 application to a private RDS MySQL database.
3. Store uploaded files in a private S3 bucket.
4. Give EC2 access to AWS services through an IAM role.
5. Run an application as a systemd service.
6. Automatically bootstrap a new EC2 instance.
7. Store application secrets outside GitHub and user data.
8. Create a Launch Template.
9. Place EC2 instances behind an Application Load Balancer.
10. Create an Auto Scaling Group across two Availability Zones.
11. Configure CPU-based target tracking.
12. Create CloudWatch alarms and SNS email notifications.
13. Verify instance replacement and data persistence.
14. Clean up AWS resources safely.

---

# 3. Prerequisites

Students should have:

- An AWS account
- Access to the AWS Console
- Basic Linux command-line knowledge
- Basic Git knowledge
- A GitHub account
- An SSH key pair
- A local computer with SSH
- The Kaizen Student Portal Git repository

Example repository:

```text
https://github.com/YOUR_GITHUB_USERNAME/kaizen-student-portal.git
```

The repository must not contain:

- `.env`
- Database passwords
- AWS access keys
- Local SQLite data
- Uploaded résumé files
- Python virtual environments

Recommended `.gitignore`:

```gitignore
.env
.venv/
instance/
__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
.DS_Store
```

The repository may include `.env.example`, but only with placeholders.

---

# 4. Application Overview

The Student Portal includes:

- Student management
- Course management
- Course registration
- Résumé upload and download
- SQLite support for local development
- MySQL support for production
- Local file storage for development
- S3 storage for production
- Flask database migrations
- Gunicorn
- Health endpoints

Important endpoints:

```text
/health
/ready
/version
/instance
```

| Endpoint | Purpose |
|---|---|
| `/health` | Confirms the Flask/Gunicorn process is responding |
| `/ready` | Confirms the application is ready and the database is reachable |
| `/version` | Displays the deployed application version |
| `/instance` | Displays the hostname or instance identity for load-balancing tests |

---

# 5. Phase 1 — Test the Application on One EC2 Instance

The first goal is to prove that the application works on EC2 before introducing RDS, S3, ALB, or Auto Scaling.

## 5.1 Launch a test EC2 instance

| Setting | Value |
|---|---|
| Name | `student-portal-test` |
| AMI | Ubuntu Server 24.04 LTS |
| Instance type | `t3.small` |
| Key pair | Your SSH key |
| Public IP | Enabled |
| Storage | 16 GiB gp3 |

For this first test, the default VPC is acceptable. Later, create the final custom VPC.

Temporary security-group rules:

| Type | Port | Source |
|---|---:|---|
| SSH | 22 | Your public IP |
| Custom TCP | 8000 | Your public IP |

## 5.2 Connect by SSH

```bash
chmod 400 ~/Downloads/YOUR_KEY.pem

ssh -i ~/Downloads/YOUR_KEY.pem \
  ubuntu@EC2_PUBLIC_IP
```

## 5.3 Install dependencies

```bash
sudo apt-get update

sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  git \
  curl
```

## 5.4 Clone the repository

```bash
git clone \
  https://github.com/YOUR_GITHUB_USERNAME/kaizen-student-portal.git

cd kaizen-student-portal
```

## 5.5 Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Important troubleshooting note

Do not rely on a global `flask` command. On some systems, it may point to an unrelated Python installation such as Anaconda.

Use:

```bash
python -m flask --app wsgi ...
```

instead of:

```bash
flask ...
```

## 5.6 Create local configuration

```bash
cp .env.example .env
nano .env
```

For the first EC2 test, use SQLite and local storage.

```dotenv
APP_NAME=Kaizen Student Portal
APP_ENV=development
SECRET_KEY=replace-with-a-random-value
LOG_LEVEL=INFO
PORT=8000

DATABASE_URL=sqlite:///instance/student_portal.db

STORAGE_BACKEND=local
LOCAL_UPLOAD_DIR=instance/uploads
MAX_UPLOAD_MB=5
```

Protect the file:

```bash
chmod 600 .env
```

## 5.7 Run database migrations

```bash
python -m flask --app wsgi db upgrade
python -m flask --app wsgi seed-db
```

## 5.8 Start Gunicorn manually

```bash
python -m gunicorn \
  -c gunicorn.conf.py \
  wsgi:app
```

Keep this terminal open. From another SSH session:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
curl -s http://127.0.0.1:8000/version
curl -s http://127.0.0.1:8000/instance
```

Open:

```text
http://EC2_PUBLIC_IP:8000
```

Create a student, a course registration, and a résumé upload. At this point, the data exists only on the EC2 instance.

---

# 6. Repository and Data Safety

## 6.1 Confirm ignored files

```bash
git status --ignored
```

Confirm these are ignored:

```text
.env
.venv/
instance/
```

## 6.2 Remove local application data from Git tracking

If `instance/` was accidentally committed:

```bash
git rm -r --cached instance/
git commit -m "Stop tracking local application data"
git push
```

Remove copied data from the EC2 test server when a clean migration test is required:

```bash
rm -rf instance/
```

Never commit SQLite files, uploaded résumés, production secrets, or virtual environments.

---

# 7. Phase 2 — Build the Final VPC

## 7.1 Create the VPC

| Setting | Value |
|---|---|
| Name | `student-portal-vpc` |
| IPv4 CIDR | `10.20.0.0/16` |

Enable DNS resolution and DNS hostnames.

## 7.2 Create public subnets

| Name | CIDR | Availability Zone |
|---|---|---|
| `student-portal-public-a` | `10.20.1.0/24` | AZ A |
| `student-portal-public-b` | `10.20.2.0/24` | AZ B |

Enable automatic public IPv4 assignment on both.

## 7.3 Create private database subnets

| Name | CIDR | Availability Zone |
|---|---|---|
| `student-portal-private-db-a` | `10.20.11.0/24` | AZ A |
| `student-portal-private-db-b` | `10.20.12.0/24` | AZ B |

Do not enable public IPv4 assignment.

## 7.4 Create and attach an Internet Gateway

Create `student-portal-igw` and attach it to `student-portal-vpc`.

## 7.5 Create route tables

### Public route table

Name: `student-portal-public-rt`

Route:

```text
0.0.0.0/0 → student-portal-igw
```

Associate both public subnets.

### Private database route table

Name: `student-portal-private-db-rt`

Keep only the local VPC route. Associate both private database subnets.

---

# 8. Security Groups

## 8.1 ALB security group

Name: `student-portal-alb-sg`

Inbound:

| Type | Port | Source |
|---|---:|---|
| HTTP | 80 | `0.0.0.0/0` |

Outbound: all traffic.

## 8.2 Application security group

Name: `student-portal-app-sg`

Inbound:

| Type | Port | Source |
|---|---:|---|
| Custom TCP | 8000 | `student-portal-alb-sg` |
| SSH | 22 | Your public IP |

During direct EC2 testing, temporarily allow port 8000 from your public IP. Remove it after ALB validation.

## 8.3 RDS security group

Name: `student-portal-rds-sg`

Inbound:

| Type | Port | Source |
|---|---:|---|
| MySQL/Aurora | 3306 | `student-portal-app-sg` |

Never allow MySQL from `0.0.0.0/0`.

---

# 9. Phase 3 — Create Amazon RDS for MySQL

## 9.1 Create a DB subnet group

Name: `student-portal-db-subnet-group`

Add both private database subnets.

## 9.2 Create the RDS instance

| Setting | Value |
|---|---|
| Engine | MySQL |
| Identifier | `student-portal-db` |
| Master username | `portal_admin` |
| Public access | No |
| VPC | `student-portal-vpc` |
| DB subnet group | `student-portal-db-subnet-group` |
| Security group | `student-portal-rds-sg` |
| Initial DB name | `student_portal` |

Save the endpoint and password securely.

## 9.3 Create an application database user

From an EC2 instance inside the VPC:

```bash
sudo apt-get update
sudo apt-get install -y mysql-client

mysql \
  -h RDS_ENDPOINT \
  -u portal_admin \
  -p
```

Create or verify the database:

```sql
SHOW DATABASES;

CREATE DATABASE IF NOT EXISTS student_portal
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

Create the application user:

```sql
CREATE USER IF NOT EXISTS 'portal_app'@'%'
IDENTIFIED BY 'REPLACE_WITH_STRONG_PASSWORD';

GRANT ALL PRIVILEGES
ON student_portal.*
TO 'portal_app'@'%';

FLUSH PRIVILEGES;
SHOW GRANTS FOR 'portal_app'@'%';
```

## 9.4 Configure the application for RDS

```dotenv
APP_ENV=production
DB_HOST=RDS_ENDPOINT
DB_PORT=3306
DB_NAME=student_portal
DB_USER=portal_app
DB_PASSWORD=REPLACE_WITH_APP_PASSWORD
```

If the application expects a full connection URL:

```dotenv
DATABASE_URL=mysql+pymysql://portal_app:PASSWORD@RDS_ENDPOINT:3306/student_portal
```

## 9.5 Run migrations

```bash
python -m flask --app wsgi db upgrade
python -m flask --app wsgi seed-db
```

## 9.6 Verify tables

```bash
mysql \
  -h RDS_ENDPOINT \
  -u portal_app \
  -p \
  student_portal
```

```sql
SHOW TABLES;
SELECT * FROM alembic_version;
SELECT COUNT(*) FROM students;
SELECT COUNT(*) FROM courses;
```

---

# 10. MySQL Migration Troubleshooting

## 10.1 Unknown database

Symptom:

```text
Unknown database 'student_portal'
```

Create it manually using the SQL shown above.

## 10.2 Migration partially created tables

A failed MySQL migration can leave some tables behind. For a fresh lab database:

```sql
DROP DATABASE student_portal;

CREATE DATABASE student_portal
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES
ON student_portal.*
TO 'portal_app'@'%';

FLUSH PRIVILEGES;
```

Then rerun the migration.

## 10.3 Index key length failure

The original `storage_key` field used `String(1024)`. With `utf8mb4` and an indexed or unique column, this exceeded MySQL index limits.

Change `String(1024)` to `String(512)` in:

```text
app/models.py
migrations/versions/0001_initial_schema.py
```

Reset the incomplete lab database and rerun migrations.

```bash
git add app/models.py migrations/versions/0001_initial_schema.py
git commit -m "Reduce storage key length for MySQL"
git push
```

---

# 11. Phase 4 — Create the S3 Bucket

## 11.1 Create a private bucket

Example:

```text
student-portal-resumes-ACCOUNT_ID-us-east-1
```

Settings:

- Block all public access
- Enable default encryption
- Disable ACLs
- Versioning optional

Use the prefix `resumes/`.

## 11.2 Create the EC2 IAM role

Role name: `student-portal-ec2-role`

Trusted service: EC2

Attach a least-privilege policy. Replace the bucket name.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListResumePrefix",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::student-portal-resumes-ACCOUNT_ID-us-east-1",
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "resumes",
            "resumes/*"
          ]
        }
      }
    },
    {
      "Sid": "ManageResumeObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::student-portal-resumes-ACCOUNT_ID-us-east-1/resumes/*"
    }
  ]
}
```

Attach the role to EC2.

## 11.3 Configure S3

```dotenv
STORAGE_BACKEND=s3
S3_BUCKET_NAME=student-portal-resumes-ACCOUNT_ID-us-east-1
AWS_REGION=us-east-1
S3_PREFIX=resumes
MAX_UPLOAD_MB=5
```

Do not configure static AWS access keys.

## 11.4 Verify the role and bucket

```bash
aws sts get-caller-identity
```

Upload a résumé through the application, then:

```bash
aws s3 ls \
  s3://student-portal-resumes-ACCOUNT_ID-us-east-1/resumes/ \
  --recursive
```

### CLI line-break troubleshooting

Do not split the command after `s3://`. Doing so runs `aws s3 ls s3://`, which attempts to list all buckets and requires `s3:ListAllMyBuckets`. The application does not need that permission.

---

# 12. Verify RDS and S3 Persistence

Start the application, create records, and upload a résumé. Restart Gunicorn and verify everything remains.

This proves:

- Relational data is in RDS
- Uploaded files are in S3
- EC2 no longer stores required persistent data

---

# 13. Phase 5 — Run the Application with systemd

Stop manually running Gunicorn and create:

```bash
sudo nano /etc/systemd/system/student-portal.service
```

```ini
[Unit]
Description=Kaizen Student Portal Gunicorn Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/kaizen-student-portal
EnvironmentFile=/home/ubuntu/kaizen-student-portal/.env
ExecStart=/home/ubuntu/kaizen-student-portal/.venv/bin/gunicorn \
  -c /home/ubuntu/kaizen-student-portal/gunicorn.conf.py \
  wsgi:app
Restart=always
RestartSec=5
TimeoutStopSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable student-portal
sudo systemctl start student-portal
sudo systemctl status student-portal --no-pager

curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
```

Logs:

```bash
sudo journalctl -u student-portal -n 100 --no-pager
sudo journalctl -u student-portal -f
```

Reboot and verify the service starts automatically.

---

# 14. Phase 6 — Store Configuration in Secrets Manager

Create:

```text
student-portal/production
```

Store these keys:

```text
APP_NAME
APP_ENV
SECRET_KEY
LOG_LEVEL
PORT
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
STORAGE_BACKEND
S3_BUCKET_NAME
AWS_REGION
S3_PREFIX
MAX_UPLOAD_MB
```

Attach this inline policy to `student-portal-ec2-role`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadStudentPortalProductionSecret",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:student-portal/production-*"
    }
  ]
}
```

Test:

```bash
aws secretsmanager get-secret-value \
  --secret-id student-portal/production \
  --region us-east-1 \
  --query ARN \
  --output text
```

Verify keys without displaying values:

```bash
aws secretsmanager get-secret-value \
  --secret-id student-portal/production \
  --region us-east-1 \
  --query SecretString \
  --output text |
python3 -c 'import json,sys; print(sorted(json.load(sys.stdin).keys()))'
```

---

# 15. Phase 7 — Create the Automated EC2 Bootstrap Script

Create `deploy/user-data.sh`:

```bash
#!/bin/bash

set -euo pipefail

exec > >(
  tee /var/log/student-portal-bootstrap.log |
  logger -t student-portal-user-data -s 2>/dev/console
) 2>&1

APP_USER="studentportal"
APP_GROUP="studentportal"
APP_DIR="/opt/student-portal"
ENV_DIR="/etc/student-portal"
ENV_FILE="${ENV_DIR}/student-portal.env"

REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/kaizen-student-portal.git"
GIT_BRANCH="main"
AWS_REGION="us-east-1"
SECRET_ID="student-portal/production"

echo "Starting Student Portal bootstrap"
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  git \
  curl \
  unzip

ARCH="$(uname -m)"

case "${ARCH}" in
  x86_64)
    AWSCLI_ARCH="x86_64"
    ;;
  aarch64|arm64)
    AWSCLI_ARCH="aarch64"
    ;;
  *)
    echo "Unsupported CPU architecture: ${ARCH}"
    exit 1
    ;;
esac

rm -rf /tmp/aws /tmp/awscliv2.zip

curl --fail --silent --show-error --location \
  "https://awscli.amazonaws.com/awscli-exe-linux-${AWSCLI_ARCH}.zip" \
  --output /tmp/awscliv2.zip

unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install --update
aws --version
rm -rf /tmp/aws /tmp/awscliv2.zip

if ! id "${APP_USER}" >/dev/null 2>&1; then
  useradd \
    --system \
    --create-home \
    --home-dir "/home/${APP_USER}" \
    --shell /usr/sbin/nologin \
    "${APP_USER}"
fi

rm -rf "${APP_DIR}"

git clone \
  --branch "${GIT_BRANCH}" \
  --depth 1 \
  "${REPO_URL}" \
  "${APP_DIR}"

python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/.venv/bin/python" -m pip install \
  -r "${APP_DIR}/requirements.txt"

install \
  -d \
  -m 0750 \
  -o root \
  -g "${APP_GROUP}" \
  "${ENV_DIR}"

SECRET_JSON="$(
  aws secretsmanager get-secret-value \
    --secret-id "${SECRET_ID}" \
    --region "${AWS_REGION}" \
    --query SecretString \
    --output text
)"

export SECRET_JSON
export ENV_FILE

python3 <<'PYTHON'
import json
import os
import shlex
from pathlib import Path

required_keys = [
    "APP_NAME",
    "APP_ENV",
    "SECRET_KEY",
    "LOG_LEVEL",
    "PORT",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "STORAGE_BACKEND",
    "S3_BUCKET_NAME",
    "AWS_REGION",
    "S3_PREFIX",
    "MAX_UPLOAD_MB",
]

secret = json.loads(os.environ["SECRET_JSON"])
missing = [key for key in required_keys if not secret.get(key)]
if missing:
    raise RuntimeError(
        "Missing required secret keys: " + ", ".join(missing)
    )

env_file = Path(os.environ["ENV_FILE"])
with env_file.open("w", encoding="utf-8") as file:
    for key in required_keys:
        file.write(f"{key}={shlex.quote(str(secret[key]))}\n")
PYTHON

unset SECRET_JSON

chown "root:${APP_GROUP}" "${ENV_FILE}"
chmod 0640 "${ENV_FILE}"
chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"

cat > /etc/systemd/system/student-portal.service <<'SERVICE'
[Unit]
Description=Kaizen Student Portal
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=studentportal
Group=studentportal
WorkingDirectory=/opt/student-portal
EnvironmentFile=/etc/student-portal/student-portal.env
ExecStart=/opt/student-portal/.venv/bin/gunicorn \
  -c /opt/student-portal/gunicorn.conf.py \
  wsgi:app
Restart=always
RestartSec=5
TimeoutStopSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable student-portal
systemctl start student-portal

echo "Waiting for application readiness"

for attempt in $(seq 1 30); do
  if curl \
    --fail \
    --silent \
    --show-error \
    http://127.0.0.1:8000/ready >/dev/null; then
    echo "Student Portal is ready"
    systemctl --no-pager status student-portal
    exit 0
  fi

  echo "Readiness attempt ${attempt}/30 failed"
  sleep 5
done

echo "Application failed readiness check"
systemctl --no-pager status student-portal || true
journalctl -u student-portal -n 100 --no-pager || true
exit 1
```

Validate and commit:

```bash
chmod +x deploy/user-data.sh
bash -n deploy/user-data.sh
git add deploy/user-data.sh
git commit -m "Add EC2 bootstrap user data"
git push
```

---

# 16. AWS CLI Installation Troubleshooting on Ubuntu 24.04

The first bootstrap attempted:

```bash
apt-get install -y awscli
```

It failed with:

```text
Package 'awscli' has no installation candidate
```

Because the script used `set -euo pipefail`, cloud-init stopped. The corrected script installs AWS CLI v2 from the official ZIP installer.

When cloud-init fails:

```bash
sudo cloud-init status --long
sudo tail -n 200 /var/log/cloud-init-output.log
sudo tail -n 200 /var/log/student-portal-bootstrap.log

sudo grep -nEi \
  'error|failed|fatal|denied|not found|traceback|unable|invalid' \
  /var/log/cloud-init-output.log \
  /var/log/student-portal-bootstrap.log

sudo sed -n '1,300p' \
  /var/lib/cloud/instance/scripts/part-001
```

Always validate the final correction on a completely fresh instance.

---

# 17. Phase 8 — Validate a Fresh Bootstrap Instance

Launch `student-portal-bootstrap-test-v2` with:

| Setting | Value |
|---|---|
| AMI | Ubuntu 24.04 |
| Type | `t3.small` |
| VPC | `student-portal-vpc` |
| Subnet | `student-portal-public-b` |
| Public IP | Enabled |
| Security group | `student-portal-app-sg` |
| IAM role | `student-portal-ec2-role` |
| Storage | 16 GiB gp3 |

Paste the corrected script into User Data.

Verify:

```bash
sudo cloud-init status --wait
sudo cloud-init status --long
aws --version
aws sts get-caller-identity
sudo systemctl is-enabled student-portal
sudo systemctl is-active student-portal
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
curl -s http://127.0.0.1:8000/version
curl -s http://127.0.0.1:8000/instance
```

Expected cloud-init result:

```text
status: done
```

Confirm existing RDS records and S3 files are visible.

---

# 18. Phase 9 — Create a Launch Template

Create `student-portal-launch-template`:

| Setting | Value |
|---|---|
| Version description | `v1 - Ubuntu bootstrap deployment` |
| AMI | Ubuntu Server 24.04 LTS |
| Architecture | x86_64 |
| Instance type | `t3.small` |
| Key pair | Existing key |
| Security group | `student-portal-app-sg` |
| Storage | 16 GiB gp3 |
| Delete on termination | Yes |
| Encryption | Enabled |
| IAM instance profile | `student-portal-ec2-role` |

Do not select a fixed subnet. Paste the corrected user-data script.

Launch one test instance from the template and verify:

```bash
sudo cloud-init status --wait
sudo systemctl is-active student-portal
curl --fail http://127.0.0.1:8000/ready
```

---

# 19. Phase 10 — Create the Target Group

Create `student-portal-tg`:

| Setting | Value |
|---|---|
| Target type | Instances |
| Protocol | HTTP |
| Port | 8000 |
| VPC | `student-portal-vpc` |
| Protocol version | HTTP1 |

Health check:

| Setting | Value |
|---|---|
| Path | `/health` |
| Success code | 200 |
| Healthy threshold | 2 |
| Unhealthy threshold | 2 |
| Timeout | 5 seconds |
| Interval | 15 seconds |

Do not manually register instances.

---

# 20. Phase 11 — Create the Application Load Balancer

Create `student-portal-alb`:

| Setting | Value |
|---|---|
| Scheme | Internet-facing |
| IP type | IPv4 |
| VPC | `student-portal-vpc` |
| Subnets | Both public subnets |
| Security group | `student-portal-alb-sg` |

Listener:

| Protocol | Port | Action |
|---|---:|---|
| HTTP | 80 | Forward to `student-portal-tg` |

A temporary 503 is expected until healthy targets exist.

---

# 21. Phase 12 — Create the Auto Scaling Group

Create `student-portal-asg` using the Launch Template.

Networking:

- `student-portal-public-a`
- `student-portal-public-b`

Attach `student-portal-tg` and enable ELB health checks.

Health-check grace period:

```text
600 seconds
```

Capacity:

| Setting | Value |
|---|---:|
| Desired | 2 |
| Minimum | 2 |
| Maximum | 4 |

Tag new instances:

```text
Name=student-portal-asg-instance
```

Wait until the target group shows two healthy targets.

---

# 22. Verify Load Balancing

```bash
ALB_DNS="YOUR_ALB_DNS_NAME"

curl -s "http://${ALB_DNS}/health"
curl -s "http://${ALB_DNS}/ready"
curl -s "http://${ALB_DNS}/version"

for i in {1..15}; do
  curl -s "http://${ALB_DNS}/instance"
  echo
  sleep 1
done
```

You should see more than one hostname.

Test student creation, registration, upload, refresh, and download through the ALB.

---

# 23. Remove Direct EC2 Port 8000 Access

Remove the temporary inbound rule allowing port 8000 from your IP.

Keep:

```text
TCP 8000 → student-portal-alb-sg
SSH 22 → Your public IP
```

Direct EC2 port 8000 should fail, while the ALB URL continues working.

---

# 24. Phase 13 — Configure CPU Target Tracking

Create `student-portal-cpu-target-tracking`:

| Setting | Value |
|---|---|
| Policy type | Target tracking |
| Metric | Average CPU utilization |
| Target | 50% |
| Instance warmup | 600 seconds |
| Scale in | Enabled |

Test on both current ASG instances:

```bash
sudo apt-get update
sudo apt-get install -y stress-ng

stress-ng \
  --cpu "$(nproc)" \
  --cpu-load 90 \
  --timeout 12m \
  --metrics-brief
```

Watch ASG Activity and target health. Let target tracking perform both scale-out and later scale-in.

---

# 25. Phase 14 — Configure SNS

Create a Standard topic:

```text
student-portal-alerts
```

Create an email subscription and confirm it. Publish a test message before connecting alarms.

---

# 26. Phase 15 — Configure CloudWatch Alarms

## 26.1 Unhealthy target alarm

Metric: `UnHealthyHostCount`

| Setting | Value |
|---|---|
| Statistic | Maximum |
| Period | 1 minute |
| Threshold | >= 1 |
| Datapoints | 2 of 2 |
| Missing data | Not breaching |

Name: `student-portal-unhealthy-targets`

Action: `student-portal-alerts`

## 26.2 Target 5XX alarm

Metric: `HTTPCode_Target_5XX_Count`

| Setting | Value |
|---|---|
| Statistic | Sum |
| Period | 5 minutes |
| Threshold | >= 5 |
| Datapoints | 1 of 1 |
| Missing data | Not breaching |

Name: `student-portal-target-5xx`

If the 5XX metric is not shown because no 5XX response has occurred, create it through CloudShell:

```bash
REGION="us-east-1"
ACCOUNT_ID="YOUR_ACCOUNT_ID"

LB_ARN="$(
  aws elbv2 describe-load-balancers \
    --names student-portal-alb \
    --region "${REGION}" \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text
)"

TG_ARN="$(
  aws elbv2 describe-target-groups \
    --names student-portal-tg \
    --region "${REGION}" \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text
)"

LB_DIM="${LB_ARN#*loadbalancer/}"
TG_DIM="${TG_ARN##*:}"
SNS_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:student-portal-alerts"

aws cloudwatch put-metric-alarm \
  --region "${REGION}" \
  --alarm-name "student-portal-target-5xx" \
  --alarm-description "Alerts when Student Portal targets return five or more server errors within five minutes." \
  --namespace "AWS/ApplicationELB" \
  --metric-name "HTTPCode_Target_5XX_Count" \
  --dimensions \
    Name=LoadBalancer,Value="${LB_DIM}" \
    Name=TargetGroup,Value="${TG_DIM}" \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --datapoints-to-alarm 1 \
  --threshold 5 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "${SNS_ARN}"
```

## 26.3 RDS CPU alarm

Metric: RDS `CPUUtilization`

| Setting | Value |
|---|---|
| Statistic | Average |
| Period | 5 minutes |
| Threshold | > 80% |
| Datapoints | 3 of 3 |
| Missing data | Not breaching |

Name: `student-portal-rds-high-cpu`

---

# 27. Phase 16 — Failure and Replacement Test

Confirm:

```text
ALB: Active
Target group: 2 Healthy
ASG desired: 2
ASG minimum: 2
ASG maximum: 4
SNS: Confirmed
Alarms: OK
```

Stop the application on one ASG instance:

```bash
sudo systemctl stop student-portal
sudo ss -lntp | grep 8000
```

Continuously test the ALB:

```bash
while true; do
  date

  curl --fail --silent \
    "http://${ALB_DNS}/health" &&
    echo " Application available" ||
    echo " Application unavailable"

  sleep 3
done
```

Expected sequence:

1. ALB stops routing to the failed target.
2. The remaining target continues serving traffic.
3. The unhealthy-target alarm enters alarm state.
4. SNS sends email.
5. ASG replaces the unhealthy instance.
6. User data configures the replacement.
7. The replacement becomes healthy.
8. The target group returns to two healthy targets.

Verify the replacement:

```bash
sudo cloud-init status --long
sudo systemctl is-active student-portal
curl --fail http://127.0.0.1:8000/ready
```

---

# 28. Persistence Test After Replacement

Through the ALB:

1. Confirm old students remain.
2. Add a new student.
3. Register the student.
4. Upload a résumé.
5. Refresh several times.
6. Download the résumé.

This confirms EC2 instances are disposable while RDS and S3 preserve state.

---

# 29. Cleanup of Temporary Resources

Terminate manually created test instances:

```text
student-portal-test
student-portal-bootstrap-test
student-portal-bootstrap-test-v2
student-portal-template-test
```

Also terminate the original manually configured EC2 after the ASG is fully working.

For a classroom demonstration, keep:

```text
Minimum: 2
Desired: 2
Maximum: 4
```

For an idle lab with lower cost:

```text
Minimum: 1
Desired: 1
Maximum: 2
```

The one-instance option removes the high-availability demonstration.

---

# 30. Complete Resource Checklist

## Networking

- [ ] VPC
- [ ] Two public subnets
- [ ] Two private DB subnets
- [ ] Internet Gateway
- [ ] Public route table
- [ ] Private DB route table

## Security

- [ ] ALB security group
- [ ] App security group
- [ ] RDS security group
- [ ] App port only from ALB SG
- [ ] MySQL only from app SG
- [ ] SSH only from your IP
- [ ] No static AWS keys
- [ ] No committed secrets

## Database and storage

- [ ] Private RDS MySQL
- [ ] `student_portal` database
- [ ] Restricted `portal_app` user
- [ ] Migrations and seed completed
- [ ] Private S3 bucket
- [ ] Résumé prefix
- [ ] IAM S3 access verified

## Deployment

- [ ] Manual EC2 test passed
- [ ] systemd test passed
- [ ] Secrets Manager configured
- [ ] User-data bootstrap passed
- [ ] Launch Template passed
- [ ] Target Group healthy
- [ ] ALB active
- [ ] ASG has two healthy instances
- [ ] Failure replacement passed

## Monitoring

- [ ] CPU target tracking
- [ ] SNS email confirmed
- [ ] Unhealthy-target alarm
- [ ] Target 5XX alarm
- [ ] RDS CPU alarm

---

# 31. Useful Troubleshooting Commands

## Application

```bash
sudo systemctl status student-portal --no-pager
sudo journalctl -u student-portal -n 100 --no-pager
curl -v http://127.0.0.1:8000/health
curl -v http://127.0.0.1:8000/ready
sudo ss -lntp | grep 8000
```

## cloud-init

```bash
sudo cloud-init status --long
sudo tail -n 200 /var/log/cloud-init-output.log
sudo tail -n 200 /var/log/student-portal-bootstrap.log
sudo sed -n '1,300p' /var/lib/cloud/instance/scripts/part-001
```

## AWS identity and secret

```bash
aws sts get-caller-identity

aws secretsmanager get-secret-value \
  --secret-id student-portal/production \
  --region us-east-1 \
  --query ARN \
  --output text
```

## S3

```bash
aws s3 ls \
  s3://student-portal-resumes-ACCOUNT_ID-us-east-1/resumes/ \
  --recursive
```

## MySQL

```bash
mysql \
  -h RDS_ENDPOINT \
  -u portal_app \
  -p \
  student_portal
```

## Target health and ASG activity

```bash
aws elbv2 describe-target-health \
  --target-group-arn TARGET_GROUP_ARN

aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name student-portal-asg \
  --max-items 10
```

---

# 32. Common Problems and Fixes

| Problem | Fix |
|---|---|
| `flask` uses wrong Python | Use the venv and `python -m flask` |
| Unknown database | Create `student_portal` manually |
| Tables already exist after failed migration | Reset the fresh lab DB and rerun |
| MySQL index key too long | Change indexed `storage_key` from 1024 to 512 |
| S3 requests `ListAllMyBuckets` | Keep the bucket URI together in the CLI command |
| cloud-init `scripts_user` failed | Read the bootstrap and cloud-init logs |
| `awscli` unavailable through APT | Install AWS CLI v2 using the ZIP installer |
| ALB returns 503 | Check target health, service, port, SG, and health path |
| Target remains unhealthy | Test `/health` locally and verify SG source |
| ASG does not replace instance | Enable ELB health checks and verify TG attachment |
| Target 5XX metric missing | Create the alarm through CloudShell |

---

# 33. Optional Bonus Topics

These are excluded from the required student lab to keep it focused:

- CloudWatch Agent
- Centralized Gunicorn and bootstrap logs
- Custom memory, disk, and swap metrics
- Route 53, ACM, and HTTPS
- Systems Manager Session Manager
- Private application subnets
- NAT Gateway or VPC endpoints
- GitHub Actions CI/CD
- Blue/green deployments
- Terraform, CloudFormation, or CDK
- RDS Multi-AZ
- Automated backups and point-in-time recovery
- Secrets rotation
- AWS WAF
- VPC Flow Logs

---

# 34. Final Student Validation

The project is complete when:

1. The application is reachable through the ALB.
2. Direct EC2 port 8000 access is blocked.
3. Two ASG instances are healthy.
4. `/instance` proves traffic reaches multiple instances.
5. Data survives EC2 restart and replacement.
6. Résumés exist in S3.
7. RDS is private.
8. S3 is private.
9. EC2 uses an IAM role.
10. Secrets are in Secrets Manager.
11. A new EC2 instance bootstraps automatically.
12. CPU target tracking can scale the ASG.
13. CloudWatch alarms notify SNS.
14. One failed instance does not make the site unavailable.
15. ASG replaces an unhealthy instance.

---

# 35. Suggested Instructor Demonstration Order

1. Explain the application locally.
2. Launch one EC2 instance.
3. Run with SQLite and local uploads.
4. Explain the problem with EC2-local state.
5. Build the custom VPC.
6. Create security groups.
7. Create private RDS.
8. Migrate the application to RDS.
9. Create private S3.
10. Attach the EC2 IAM role.
11. Verify S3 uploads.
12. Run the app using systemd.
13. Move secrets to Secrets Manager.
14. Build and troubleshoot user data.
15. Validate a fresh EC2 bootstrap.
16. Create the Launch Template.
17. Create the Target Group.
18. Create the ALB.
19. Create the ASG.
20. Verify load balancing.
21. Remove direct port 8000 access.
22. Add CPU target tracking.
23. Add SNS and CloudWatch alarms.
24. Stop the app on one instance.
25. Observe ALB routing and ASG replacement.
26. Verify RDS and S3 persistence.
27. Clean up temporary resources.
28. Discuss optional production improvements.

This order helps students understand why each AWS service is introduced instead of presenting the final architecture without context.

