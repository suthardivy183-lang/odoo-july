from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_esg
from app.db.session import get_db
from app.models.core import Department, User
from app.models.enums import RedemptionStatus, Role
from app.models.gamification import XPTransaction
from app.models.masterdata import Reward, RewardRedemption, UserBadge
from app.schemas.common import Page, UserBrief
from app.schemas.gamification import (
    LeaderboardEntry,
    LeaderboardOut,
    RedeemIn,
    RedemptionOut,
    XPSummaryOut,
    XPTransactionOut,
)
from app.services.xp import (
    XPError,
    approved_challenge_count,
    approved_csr_count,
    cancel_redemption,
    fulfill_redemption,
    lifetime_earned_xp,
    redeem_reward,
    return_redemption,
)
from app.utils.time import date_to_utc_range, month_bounds, week_bounds

router = APIRouter(tags=["Gamification"])


@router.get("/gamification/me", response_model=XPSummaryOut)
def my_summary(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    badges = db.execute(
        select(func.count(UserBadge.id)).where(UserBadge.user_id == current.id)
    ).scalar_one()
    return XPSummaryOut(
        xp_balance=current.xp_balance,
        lifetime_earned=lifetime_earned_xp(db, current.id),
        approved_challenges=approved_challenge_count(db, current.id),
        approved_csr=approved_csr_count(db, current.id),
        badges_count=badges,
    )


@router.get("/gamification/transactions", response_model=Page[XPTransactionOut])
def xp_transactions(
    user_id: int | None = None,
    page: int = 1,
    size: int = Query(20, le=100),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_id = current.id
    if user_id is not None and user_id != current.id:
        if current.role not in (Role.esg_manager, Role.admin):
            raise HTTPException(status_code=403, detail="You can only view your own XP history")
        target_id = user_id
    stmt = select(XPTransaction).where(XPTransaction.user_id == target_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(XPTransaction.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return Page[XPTransactionOut](items=rows, total=total)


@router.get("/gamification/leaderboard", response_model=LeaderboardOut)
def leaderboard(
    period: Literal["weekly", "monthly", "all"] = "all",
    limit: int = Query(50, le=100),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rank by XP EARNED (positive transactions) in the period; ties share a rank."""
    start = end = None
    stmt = (
        select(User, func.coalesce(func.sum(XPTransaction.amount), 0).label("xp"))
        .join(XPTransaction, XPTransaction.user_id == User.id)
        .where(User.is_active.is_(True), XPTransaction.amount > 0)
        .group_by(User.id)
    )
    if period != "all":
        start, end = week_bounds() if period == "weekly" else month_bounds()
        utc_start, utc_end = date_to_utc_range(start, end)
        stmt = stmt.where(
            XPTransaction.created_at >= utc_start, XPTransaction.created_at < utc_end
        )
    rows = db.execute(stmt.order_by(func.sum(XPTransaction.amount).desc())).all()

    dept_names = {
        d.id: d.name for d in db.execute(select(Department)).scalars().all()
    }
    entries: list[LeaderboardEntry] = []
    my_rank: int | None = None
    my_xp = 0
    rank = 0
    prev_xp: int | None = None
    for position, (user, xp) in enumerate(rows, start=1):
        if xp != prev_xp:
            rank = position  # competition ranking: ties share, next rank skips
            prev_xp = xp
        if user.id == current.id:
            my_rank = rank
            my_xp = int(xp)
        if position <= limit:
            entries.append(
                LeaderboardEntry(
                    rank=rank,
                    user=UserBrief.model_validate(user),
                    department_name=dept_names.get(user.department_id),
                    xp=int(xp),
                )
            )
    return LeaderboardOut(
        period=period, start_date=start, end_date=end,
        entries=entries, my_rank=my_rank, my_xp=my_xp,
    )


def _redemption_out(r: RewardRedemption) -> RedemptionOut:
    out = RedemptionOut.model_validate(r)
    out.reward_name = r.reward.name if r.reward else None
    return out


def _get_redemption(db: Session, redemption_id: int) -> RewardRedemption:
    r = db.execute(
        select(RewardRedemption)
        .options(joinedload(RewardRedemption.reward), joinedload(RewardRedemption.user))
        .where(RewardRedemption.id == redemption_id)
    ).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Redemption not found")
    return r


@router.post("/gamification/redemptions", response_model=RedemptionOut, status_code=201)
def redeem(
    payload: RedeemIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.get(Reward, payload.reward_id) is None:
        raise HTTPException(status_code=404, detail="Reward not found")
    try:
        redemption = redeem_reward(db, current, payload.reward_id)
    except XPError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return _redemption_out(_get_redemption(db, redemption.id))


@router.get("/gamification/redemptions/me", response_model=list[RedemptionOut])
def my_redemptions(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(RewardRedemption)
            .options(joinedload(RewardRedemption.reward), joinedload(RewardRedemption.user))
            .where(RewardRedemption.user_id == current.id)
            .order_by(RewardRedemption.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_redemption_out(r) for r in rows]


@router.get("/gamification/redemptions", response_model=Page[RedemptionOut])
def list_redemptions(
    status: RedemptionStatus | None = None,
    user_id: int | None = None,
    page: int = 1,
    size: int = Query(20, le=100),
    _: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    stmt = select(RewardRedemption)
    if status is not None:
        stmt = stmt.where(RewardRedemption.status == status)
    if user_id is not None:
        stmt = stmt.where(RewardRedemption.user_id == user_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.options(joinedload(RewardRedemption.reward), joinedload(RewardRedemption.user))
            .order_by(RewardRedemption.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return Page[RedemptionOut](items=[_redemption_out(r) for r in rows], total=total)


@router.post("/gamification/redemptions/{redemption_id}/cancel", response_model=RedemptionOut)
def cancel(
    redemption_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    redemption = _get_redemption(db, redemption_id)
    is_owner = redemption.user_id == current.id
    if not is_owner and current.role not in (Role.esg_manager, Role.admin):
        raise HTTPException(status_code=403, detail="You cannot cancel this redemption")
    try:
        cancel_redemption(db, redemption, current.id)
    except XPError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return _redemption_out(_get_redemption(db, redemption.id))


@router.post("/gamification/redemptions/{redemption_id}/fulfill", response_model=RedemptionOut)
def fulfill(
    redemption_id: int,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    redemption = _get_redemption(db, redemption_id)
    try:
        fulfill_redemption(db, redemption, current.id)
    except XPError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return _redemption_out(_get_redemption(db, redemption.id))


@router.post("/gamification/redemptions/{redemption_id}/return", response_model=RedemptionOut)
def mark_returned(
    redemption_id: int,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    redemption = _get_redemption(db, redemption_id)
    try:
        return_redemption(db, redemption, current.id)
    except XPError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return _redemption_out(_get_redemption(db, redemption.id))
