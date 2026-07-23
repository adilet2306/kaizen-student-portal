from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class StorageConfigurationError(RuntimeError):
    pass


class StorageOperationError(RuntimeError):
    pass


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]
    )


def build_storage_key(student_id: int, filename: str) -> str:
    safe_name = secure_filename(filename)
    prefix = current_app.config["S3_PREFIX"]
    unique_name = f"{uuid.uuid4().hex}-{safe_name}"
    return f"{prefix}/{student_id}/{unique_name}" if prefix else f"{student_id}/{unique_name}"


def save_upload(file: FileStorage, student_id: int) -> tuple[str, str, int]:
    if not file or not file.filename:
        raise StorageOperationError("No file was selected.")

    if not allowed_file(file.filename):
        allowed = ", ".join(sorted(current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]))
        raise StorageOperationError(f"Unsupported file type. Allowed: {allowed}.")

    storage_key = build_storage_key(student_id, file.filename)
    content_type = (
        file.mimetype
        or mimetypes.guess_type(file.filename)[0]
        or "application/octet-stream"
    )

    file.stream.seek(0, 2)
    size_bytes = file.stream.tell()
    file.stream.seek(0)

    backend = current_app.config["STORAGE_BACKEND"]

    if backend == "local":
        destination = Path(current_app.config["UPLOAD_FOLDER"]) / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        file.save(destination)
        return storage_key, content_type, size_bytes

    if backend != "s3":
        raise StorageConfigurationError(
            f"Unknown STORAGE_BACKEND value: {backend}"
        )

    bucket = current_app.config["S3_BUCKET_NAME"]
    if not bucket:
        raise StorageConfigurationError(
            "S3_BUCKET_NAME is required when STORAGE_BACKEND=s3."
        )

    client = boto3.client("s3", region_name=current_app.config["AWS_REGION"])

    try:
        client.upload_fileobj(
            file.stream,
            bucket,
            storage_key,
            ExtraArgs={"ContentType": content_type},
        )
    except (BotoCoreError, ClientError) as error:
        current_app.logger.exception(
            "s3_upload_failed bucket=%s key=%s",
            bucket,
            storage_key,
        )
        raise StorageOperationError("The file could not be uploaded to S3.") from error

    return storage_key, content_type, size_bytes


def create_download_target(storage_key: str):
    backend = current_app.config["STORAGE_BACKEND"]

    if backend == "local":
        return {
            "backend": "local",
            "path": Path(current_app.config["UPLOAD_FOLDER"]) / storage_key,
        }

    if backend != "s3":
        raise StorageConfigurationError(
            f"Unknown STORAGE_BACKEND value: {backend}"
        )

    bucket = current_app.config["S3_BUCKET_NAME"]
    if not bucket:
        raise StorageConfigurationError(
            "S3_BUCKET_NAME is required when STORAGE_BACKEND=s3."
        )

    client = boto3.client("s3", region_name=current_app.config["AWS_REGION"])

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": storage_key},
            ExpiresIn=900,
        )
    except (BotoCoreError, ClientError) as error:
        current_app.logger.exception(
            "s3_presigned_url_failed bucket=%s key=%s",
            bucket,
            storage_key,
        )
        raise StorageOperationError("A download link could not be created.") from error

    return {"backend": "s3", "url": url}
