"""Policy acknowledgement reminders.

For each published policy, users without an acknowledgement of the CURRENT
version get a reminder when the deadline is within 3 days or already past.
De-duplicated to at most one reminder per user/policy per IST day. Runs daily
from the scheduler and on demand from the "send reminders" endpoint.
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Notification, User
from app.models.enums import NotificationType, PolicyStatus
from app.models.masterdata import ESGPolicy, PolicyAcknowledgement
from app.services.notify import notify
from app.utils.time import IST, date_to_utc_range, today_ist

REMINDER_WINDOW_DAYS = 3


def ack_deadline(policy: ESGPolicy) -> dt.date | None:
    if policy.published_at is None:
        return None
    return policy.published_at.astimezone(IST).date() + dt.timedelta(
        days=policy.ack_deadline_days
    )


def pending_user_ids(db: Session, policy: ESGPolicy) -> set[int]:
    """Active users who have NOT acknowledged the current version."""
    all_ids = set(
        db.execute(select(User.id).where(User.is_active.is_(True))).scalars().all()
    )
    acked = set(
        db.execute(
            select(PolicyAcknowledgement.user_id).where(
                PolicyAcknowledgement.policy_id == policy.id,
                PolicyAcknowledgement.policy_version == policy.version,
            )
        )
        .scalars()
        .all()
    )
    return all_ids - acked


def send_policy_reminders(db: Session, force: bool = False) -> int:
    """Send due reminders. force=True ignores the 3-day window (manual button).

    Returns the number of reminder notifications sent.
    """
    today = today_ist()
    start_utc, end_utc = date_to_utc_range(today, today)
    policies = (
        db.execute(select(ESGPolicy).where(ESGPolicy.status == PolicyStatus.published))
        .scalars()
        .all()
    )
    sent = 0
    for policy in policies:
        deadline = ack_deadline(policy)
        if deadline is None:
            continue
        days_left = (deadline - today).days
        if not force and days_left > REMINDER_WINDOW_DAYS:
            continue
        pending = pending_user_ids(db, policy)
        if not pending:
            continue
        # de-dupe: skip users already reminded today for this policy
        reminded_today = set(
            db.execute(
                select(Notification.user_id).where(
                    Notification.type == NotificationType.policy_reminder,
                    Notification.entity_type == "policy",
                    Notification.entity_id == policy.id,
                    Notification.created_at >= start_utc,
                    Notification.created_at < end_utc,
                )
            )
            .scalars()
            .all()
        )
        targets = [
            u for u in db.execute(
                select(User).where(User.id.in_(pending - reminded_today))
            ).scalars().all()
        ]
        if not targets:
            continue
        if days_left >= 0:
            body = (
                f"Please acknowledge policy '{policy.title}' (v{policy.version}) "
                f"by {deadline.isoformat()} — {days_left} day(s) left."
            )
        else:
            body = (
                f"Acknowledgement of policy '{policy.title}' (v{policy.version}) is "
                f"{-days_left} day(s) OVERDUE (deadline {deadline.isoformat()})."
            )
        sent += notify(
            db, targets, NotificationType.policy_reminder,
            f"Action required: acknowledge '{policy.title}'", body,
            entity_type="policy", entity_id=policy.id,
        )
    return sent
