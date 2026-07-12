import datetime as dt

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    title: str
    body: str
    entity_type: str | None = None
    entity_id: int | None = None
    is_read: bool
    created_at: dt.datetime


class MarkReadIn(BaseModel):
    ids: list[int] = []


class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    to_email: str
    subject: str
    body: str
    notif_type: str
    created_at: dt.datetime
