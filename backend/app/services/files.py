"""Local-disk upload storage with strict backend validation.

Accepted: JPG / PNG / PDF, max 10 MB. Extension AND magic bytes are checked.
Files land under uploads/YYYY/MM/<uuid>.<ext>; metadata in attachments table.
"""

import uuid

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.core import Attachment, User
from app.utils.time import now_ist

MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAGIC_SIGNATURES = {
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "pdf": [b"%PDF"],
}
MIME_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "pdf": "application/pdf",
}


class FileValidationError(Exception):
    """Maps to HTTP 400 in routers."""


def save_upload(
    db: Session,
    file: UploadFile,
    user: User,
    context: str = "other",
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> Attachment:
    name = file.filename or "upload"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError("Only JPG, PNG and PDF files are accepted")

    content = file.file.read(MAX_SIZE_BYTES + 1)
    if len(content) > MAX_SIZE_BYTES:
        raise FileValidationError("File exceeds the 10 MB size limit")
    if len(content) == 0:
        raise FileValidationError("Uploaded file is empty")
    if not any(content.startswith(sig) for sig in MAGIC_SIGNATURES[ext]):
        raise FileValidationError(
            "File content does not match its extension (expected JPG, PNG or PDF)"
        )

    today = now_ist()
    rel_dir = f"{today.year:04d}/{today.month:02d}"
    target_dir = settings.upload_path / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    (target_dir / stored_name).write_bytes(content)

    attachment = Attachment(
        original_name=name[:255],
        stored_path=f"{rel_dir}/{stored_name}",
        mime=MIME_BY_EXT[ext],
        size_bytes=len(content),
        uploaded_by=user.id,
        context=context[:40],
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(attachment)
    db.flush()
    return attachment


def absolute_path(attachment: Attachment) -> str:
    return str(settings.upload_path / attachment.stored_path)
