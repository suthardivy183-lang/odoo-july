from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import Attachment, User
from app.schemas.common import AttachmentOut
from app.services.files import FileValidationError, absolute_path, save_upload

router = APIRouter(prefix="/files", tags=["Files"])


@router.post("", response_model=AttachmentOut)
def upload_file(
    file: UploadFile,
    context: str = Form("other"),
    entity_type: str | None = Form(None),
    entity_id: int | None = Form(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        attachment = save_upload(
            db, file, current, context=context, entity_type=entity_type, entity_id=entity_id
        )
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("/{attachment_id}")
def download_file(
    attachment_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        absolute_path(attachment),
        media_type=attachment.mime,
        filename=attachment.original_name,
        content_disposition_type="inline",
    )
