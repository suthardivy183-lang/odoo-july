from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_esg
from app.db.session import get_db
from app.models.core import EmailLog, Notification, User
from app.schemas.common import Msg, Page
from app.schemas.notifications import EmailLogOut, MarkReadIn, NotificationOut

router = APIRouter(tags=["Notifications"])


@router.get("/notifications/me", response_model=Page[NotificationOut])
def my_notifications(
    unread_only: bool = False,
    page: int = 1,
    size: int = Query(20, le=100),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == current.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(Notification.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return Page[NotificationOut](items=rows, total=total)


@router.get("/notifications/me/unread-count")
def unread_count(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current.id, Notification.is_read.is_(False)
        )
    ).scalar_one()
    return {"unread": count}


@router.post("/notifications/me/read", response_model=Msg)
def mark_read(
    payload: MarkReadIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark the given notification ids as read; empty list marks ALL as read."""
    stmt = (
        update(Notification)
        .where(Notification.user_id == current.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    if payload.ids:
        stmt = stmt.where(Notification.id.in_(payload.ids))
    result = db.execute(stmt)
    db.commit()
    return Msg(detail=f"{result.rowcount} notification(s) marked as read")


@router.get("/notifications/email-logs", response_model=Page[EmailLogOut])
def email_logs(
    q: str | None = None,
    notif_type: str | None = None,
    page: int = 1,
    size: int = Query(20, le=100),
    _: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    stmt = select(EmailLog)
    if q:
        stmt = stmt.where(
            EmailLog.subject.ilike(f"%{q}%") | EmailLog.to_email.ilike(f"%{q}%")
        )
    if notif_type:
        stmt = stmt.where(EmailLog.notif_type == notif_type)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(EmailLog.created_at.desc()).offset((page - 1) * size).limit(size)
        )
        .scalars()
        .all()
    )
    return Page[EmailLogOut](items=rows, total=total)
