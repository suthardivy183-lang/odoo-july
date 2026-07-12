"""XP ledger + reward redemption. The only place balances and stock change.

Concurrency rules:
- users.xp_balance is only mutated together with an XPTransaction insert,
  under SELECT ... FOR UPDATE on the user row.
- Reward stock is only mutated under SELECT ... FOR UPDATE on the reward row.
- Services flush; the calling router commits (single transaction per request).
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import User
from app.models.enums import (
    AuditAction,
    ParticipationStatus,
    RedemptionStatus,
    XPType,
)
from app.models.gamification import ChallengeParticipation, XPTransaction
from app.models.masterdata import Reward, RewardRedemption
from app.models.social import CSRParticipation
from app.services.audit import log_action


class XPError(Exception):
    """Business-rule violation (maps to HTTP 400 in routers)."""


def _locked_user(db: Session, user_id: int) -> User:
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise XPError("User not found")
    return user


def apply_xp(
    db: Session,
    user_id: int,
    amount: int,
    xp_type: XPType,
    description: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> XPTransaction:
    """Atomically apply a signed XP amount and record the ledger entry."""
    user = _locked_user(db, user_id)
    new_balance = user.xp_balance + amount
    if new_balance < 0:
        raise XPError("Insufficient points")
    user.xp_balance = new_balance
    txn = XPTransaction(
        user_id=user_id,
        amount=amount,
        type=xp_type,
        ref_type=ref_type,
        ref_id=ref_id,
        description=description[:255],
        balance_after=new_balance,
    )
    db.add(txn)
    db.flush()
    return txn


def award_once_for_challenge(db: Session, participation_id: int, actor_id: int | None) -> bool:
    """Award challenge XP exactly once. Returns False if already awarded."""
    part = db.execute(
        select(ChallengeParticipation)
        .where(ChallengeParticipation.id == participation_id)
        .with_for_update()
    ).scalar_one()
    if part.xp_awarded is not None:
        return False
    amount = part.challenge.xp
    apply_xp(
        db,
        part.user_id,
        amount,
        XPType.challenge_award,
        f"Challenge approved: {part.challenge.title}",
        ref_type="challenge_participation",
        ref_id=part.id,
    )
    part.xp_awarded = amount
    part.progress = 100
    part.completion_date = dt.date.today()
    log_action(
        db, actor_id, AuditAction.award_xp, "challenge_participation", part.id,
        entity_label=part.challenge.title, after={"xp_awarded": amount},
    )
    return True


def award_once_for_csr(db: Session, participation_id: int, actor_id: int | None) -> bool:
    """Award CSR points exactly once. Returns False if already awarded."""
    part = db.execute(
        select(CSRParticipation)
        .where(CSRParticipation.id == participation_id)
        .with_for_update()
    ).scalar_one()
    if part.points_earned is not None:
        return False
    amount = part.activity.points
    apply_xp(
        db,
        part.user_id,
        amount,
        XPType.csr_award,
        f"CSR activity approved: {part.activity.title}",
        ref_type="csr_participation",
        ref_id=part.id,
    )
    part.points_earned = amount
    part.completion_date = dt.date.today()
    log_action(
        db, actor_id, AuditAction.award_xp, "csr_participation", part.id,
        entity_label=part.activity.title, after={"points_earned": amount},
    )
    return True


def _locked_reward(db: Session, reward_id: int) -> Reward:
    reward = db.execute(
        select(Reward).where(Reward.id == reward_id).with_for_update()
    ).scalar_one_or_none()
    if reward is None:
        raise XPError("Reward not found")
    return reward


def redeem_reward(db: Session, user: User, reward_id: int) -> RewardRedemption:
    """Atomic: validate stock + balance, deduct both, create redemption."""
    reward = _locked_reward(db, reward_id)
    if reward.status.value != "active":
        raise XPError("Reward is not active")
    if reward.stock < 1:
        raise XPError("Reward is out of stock")
    apply_xp(
        db, user.id, -reward.points_cost, XPType.redeem_spend,
        f"Redeemed reward: {reward.name}", ref_type="reward", ref_id=reward.id,
    )
    reward.stock -= 1
    redemption = RewardRedemption(
        user_id=user.id, reward_id=reward.id, points_spent=reward.points_cost,
        status=RedemptionStatus.placed,
    )
    db.add(redemption)
    db.flush()
    log_action(
        db, user.id, AuditAction.redeem, "reward_redemption", redemption.id,
        entity_label=reward.name,
        after={"points_spent": reward.points_cost, "stock_left": reward.stock},
    )
    return redemption


def cancel_redemption(db: Session, redemption: RewardRedemption, actor_id: int) -> None:
    """placed -> cancelled: refund points AND restore stock."""
    if redemption.status != RedemptionStatus.placed:
        raise XPError("Only placed redemptions can be cancelled")
    reward = _locked_reward(db, redemption.reward_id)
    apply_xp(
        db, redemption.user_id, redemption.points_spent, XPType.redeem_refund,
        f"Refund for cancelled redemption: {reward.name}",
        ref_type="reward_redemption", ref_id=redemption.id,
    )
    reward.stock += 1
    redemption.status = RedemptionStatus.cancelled
    log_action(
        db, actor_id, AuditAction.cancel, "reward_redemption", redemption.id,
        entity_label=reward.name,
        after={"refunded": redemption.points_spent, "stock": reward.stock},
    )


def fulfill_redemption(db: Session, redemption: RewardRedemption, actor_id: int) -> None:
    if redemption.status != RedemptionStatus.placed:
        raise XPError("Only placed redemptions can be fulfilled")
    redemption.status = RedemptionStatus.fulfilled
    log_action(
        db, actor_id, AuditAction.fulfill, "reward_redemption", redemption.id,
        entity_label=redemption.reward.name,
    )


def return_redemption(db: Session, redemption: RewardRedemption, actor_id: int) -> None:
    """fulfilled -> returned: restore stock AND refund points."""
    if redemption.status != RedemptionStatus.fulfilled:
        raise XPError("Only fulfilled redemptions can be returned")
    reward = _locked_reward(db, redemption.reward_id)
    reward.stock += 1
    apply_xp(
        db, redemption.user_id, redemption.points_spent, XPType.redeem_refund,
        f"Refund for returned reward: {reward.name}",
        ref_type="reward_redemption", ref_id=redemption.id,
    )
    redemption.status = RedemptionStatus.returned
    log_action(
        db, actor_id, AuditAction.returned, "reward_redemption", redemption.id,
        entity_label=reward.name,
        after={"refunded": redemption.points_spent, "stock": reward.stock},
    )


def lifetime_earned_xp(db: Session, user_id: int) -> int:
    from sqlalchemy import func as safunc

    total = db.execute(
        select(safunc.coalesce(safunc.sum(XPTransaction.amount), 0)).where(
            XPTransaction.user_id == user_id, XPTransaction.amount > 0
        )
    ).scalar_one()
    return int(total)


def approved_challenge_count(db: Session, user_id: int) -> int:
    from sqlalchemy import func as safunc

    return int(
        db.execute(
            select(safunc.count(ChallengeParticipation.id)).where(
                ChallengeParticipation.user_id == user_id,
                ChallengeParticipation.status == ParticipationStatus.approved,
            )
        ).scalar_one()
    )


def approved_csr_count(db: Session, user_id: int) -> int:
    from sqlalchemy import func as safunc

    return int(
        db.execute(
            select(safunc.count(CSRParticipation.id)).where(
                CSRParticipation.user_id == user_id,
                CSRParticipation.status == ParticipationStatus.approved,
            )
        ).scalar_one()
    )
