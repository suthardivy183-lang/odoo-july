"""Automatic overdue rule for compliance issues.

When due_date (IST) has passed and the issue is still open/in progress:
flag it overdue (once) and notify Owner + responsible Department Head + all
ESG Managers. Runs from the scheduler every few minutes and from the manual
"run overdue check" endpoint.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import User
from app.models.enums import AuditAction, IssueStatus, NotificationType, Role
from app.models.governance import ComplianceIssue
from app.services.audit import log_action
from app.services.notify import notify
from app.services.org import responsible_head
from app.utils.time import now_utc, today_ist


def run_overdue_check(db: Session) -> int:
    """Flag newly-overdue issues and notify. Returns number flagged."""
    today = today_ist()
    issues = (
        db.execute(
            select(ComplianceIssue).where(
                ComplianceIssue.status.in_([IssueStatus.open, IssueStatus.in_progress]),
                ComplianceIssue.due_date < today,
                ComplianceIssue.is_overdue.is_(False),
            )
        )
        .scalars()
        .all()
    )
    esg_managers = (
        db.execute(
            select(User).where(User.role == Role.esg_manager, User.is_active.is_(True))
        )
        .scalars()
        .all()
    )
    for issue in issues:
        issue.is_overdue = True
        issue.overdue_notified_at = now_utc()
        recipients: list[User] = []
        owner = db.get(User, issue.owner_user_id)
        if owner:
            recipients.append(owner)
        head = responsible_head(db, issue.department_id)
        if head:
            recipients.append(head)
        recipients.extend(esg_managers)
        days_over = (today - issue.due_date).days
        notify(
            db,
            recipients,
            NotificationType.compliance_overdue,
            f"Compliance issue overdue: {issue.title}",
            f"Severity {issue.severity.value.upper()} issue '{issue.title}' was due "
            f"{issue.due_date.isoformat()} and is now {days_over} day(s) overdue. "
            f"Status: {issue.status.value}.",
            entity_type="compliance_issue",
            entity_id=issue.id,
        )
        log_action(
            db, None, AuditAction.status_change, "compliance_issue", issue.id,
            entity_label=issue.title,
            before={"is_overdue": False}, after={"is_overdue": True},
        )
    return len(issues)


def refresh_overdue_flag(issue: ComplianceIssue) -> None:
    """Clear the overdue flag when an issue is resolved/closed or re-dated.

    Call from the update/transition endpoints after mutating due_date/status.
    """
    if issue.status in (IssueStatus.resolved, IssueStatus.closed):
        issue.is_overdue = False
    elif issue.due_date >= today_ist():
        issue.is_overdue = False
        issue.overdue_notified_at = None
