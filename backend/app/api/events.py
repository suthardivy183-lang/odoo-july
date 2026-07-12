import datetime as dt

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import User
from app.models.events import DomainEvent

router = APIRouter(tags=["Events"])


class DomainEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    department_id: int | None
    entity_type: str | None
    entity_id: int | None
    actor_id: int | None
    payload: dict
    created_at: dt.datetime


@router.get("/events/recent", response_model=list[DomainEventOut])
def recent_events(
    limit: int = Query(20, ge=1, le=100),
    department_id: int | None = None,
    _current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(DomainEvent).order_by(DomainEvent.created_at.desc(), DomainEvent.id.desc())
    if department_id is not None:
        query = query.where(DomainEvent.department_id == department_id)
    return list(db.scalars(query.limit(limit)).all())
