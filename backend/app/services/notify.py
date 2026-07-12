"""In-app + mock-email notification dispatcher.

Honors the per-event, per-channel toggles in org settings. Mock email is a row
in email_logs (never a real send). Callers commit.
"""

from sqlalchemy.orm import Session

from app.models.core import EmailLog, Notification, User
from app.models.enums import NotificationType
from app.services.org_settings import channel_prefs, get_org_settings


def notify(
    db: Session,
    users: list[User] | User,
    ntype: NotificationType,
    title: str,
    body: str = "",
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> int:
    """Send a notification to one or more users. Returns count delivered (in-app)."""
    if isinstance(users, User):
        users = [users]
    # de-dupe recipients (e.g. owner == dept head)
    seen: set[int] = set()
    recipients = []
    for u in users:
        if u is not None and u.id not in seen and u.is_active:
            seen.add(u.id)
            recipients.append(u)

    settings_row = get_org_settings(db)
    prefs = channel_prefs(settings_row, ntype)
    delivered = 0
    for u in recipients:
        if prefs["in_app"]:
            db.add(
                Notification(
                    user_id=u.id,
                    type=ntype,
                    title=title[:200],
                    body=body,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
            )
            delivered += 1
        if prefs["email"]:
            db.add(
                EmailLog(
                    to_user_id=u.id,
                    to_email=u.email,
                    subject=f"[EcoSphere] {title}"[:300],
                    body=body or title,
                    notif_type=ntype.value,
                )
            )
    return delivered
