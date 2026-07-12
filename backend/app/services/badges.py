"""Badge engine: automatic unlock evaluation + manual assignment.

Auto rules: xp_threshold (lifetime earned XP), challenge_count (approved
challenge participations), csr_count (approved CSR participations).
Evaluation runs after XP awards / approvals, on an hourly sweep, and via the
manual "re-evaluate" endpoint. Respects the org "Badge Auto Award" toggle.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import User
from app.models.enums import ActiveStatus, AuditAction, BadgeRule, NotificationType
from app.models.masterdata import Badge, UserBadge
from app.services.audit import log_action
from app.services.notify import notify
from app.services.org_settings import get_org_settings
from app.services.xp import (
    approved_challenge_count,
    approved_csr_count,
    lifetime_earned_xp,
)


def _grant(db: Session, user: User, badge: Badge, actor_id: int | None) -> UserBadge:
    ub = UserBadge(user_id=user.id, badge_id=badge.id, awarded_by=actor_id)
    db.add(ub)
    db.flush()
    log_action(
        db, actor_id, AuditAction.award_badge, "user_badge", ub.id,
        entity_label=f"{badge.name} -> {user.full_name}",
        after={"badge_id": badge.id, "user_id": user.id},
    )
    notify(
        db, user, NotificationType.badge_unlocked,
        f"Badge unlocked: {badge.icon} {badge.name}",
        badge.description or f"You earned the {badge.name} badge!",
        entity_type="badge", entity_id=badge.id,
    )
    return ub


def evaluate_user_badges(db: Session, user: User) -> list[Badge]:
    """Award every auto badge the user now qualifies for. Returns new badges."""
    settings_row = get_org_settings(db)
    if not settings_row.badge_auto_award:
        return []
    owned = set(
        db.execute(select(UserBadge.badge_id).where(UserBadge.user_id == user.id))
        .scalars()
        .all()
    )
    candidates = (
        db.execute(
            select(Badge).where(
                Badge.status == ActiveStatus.active,
                Badge.rule_type != BadgeRule.manual,
            )
        )
        .scalars()
        .all()
    )
    metrics: dict[BadgeRule, int] = {}
    awarded: list[Badge] = []
    for badge in candidates:
        if badge.id in owned or badge.rule_value is None:
            continue
        if badge.rule_type not in metrics:
            if badge.rule_type == BadgeRule.xp_threshold:
                metrics[badge.rule_type] = lifetime_earned_xp(db, user.id)
            elif badge.rule_type == BadgeRule.challenge_count:
                metrics[badge.rule_type] = approved_challenge_count(db, user.id)
            elif badge.rule_type == BadgeRule.csr_count:
                metrics[badge.rule_type] = approved_csr_count(db, user.id)
        if metrics.get(badge.rule_type, 0) >= badge.rule_value:
            _grant(db, user, badge, actor_id=None)
            awarded.append(badge)
    return awarded


def assign_badge_manual(db: Session, user: User, badge: Badge, actor_id: int) -> UserBadge | None:
    """Admin manual assignment. Returns None if the user already has it."""
    existing = db.execute(
        select(UserBadge).where(
            UserBadge.user_id == user.id, UserBadge.badge_id == badge.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None
    return _grant(db, user, badge, actor_id=actor_id)


def sweep_all(db: Session) -> int:
    """Evaluate every active user (hourly safety net). Returns badges awarded."""
    users = db.execute(select(User).where(User.is_active.is_(True))).scalars().all()
    count = 0
    for user in users:
        count += len(evaluate_user_badges(db, user))
    return count
