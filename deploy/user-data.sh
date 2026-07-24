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

REPO_URL="https://github.com/adilet2306/kaizen-student-portal.git"
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
