from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_esg
from app.db.session import get_db
from app.models.core import User
from app.models.enums import ActiveStatus, AuditAction
from app.models.masterdata import Reward, RewardRedemption
from app.schemas.common import Msg, Page
from app.schemas.rewards import RewardCreate, RewardOut, RewardUpdate
from app.services.audit import log_action, snapshot

router = APIRouter(tags=["Rewards"])

AUDIT_FIELDS = ["name", "description", "points_cost", "stock", "status"]


def _redeemed_counts(db: Session, reward_ids: list[int]) -> dict[int, int]:
    if not reward_ids:
        return {}
    rows = db.execute(
        select(RewardRedemption.reward_id, func.count(RewardRedemption.id))
        .where(RewardRedemption.reward_id.in_(reward_ids))
        .group_by(RewardRedemption.reward_id)
    ).all()
    return {reward_id: count for reward_id, count in rows}


def _reward_out(reward: Reward, counts: dict[int, int]) -> RewardOut:
    out = RewardOut.model_validate(reward)
    out.redeemed_count = counts.get(reward.id, 0)
    return out


@router.get("/rewards", response_model=Page[RewardOut])
def list_rewards(
    status: ActiveStatus | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = Query(50, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Reward)
    if status is not None:
        stmt = stmt.where(Reward.status == status)
    if q:
        stmt = stmt.where(Reward.name.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rewards = (
        db.execute(
            stmt.order_by(Reward.points_cost.asc()).offset((page - 1) * size).limit(size)
        )
        .scalars()
        .all()
    )
    counts = _redeemed_counts(db, [r.id for r in rewards])
    return Page[RewardOut](items=[_reward_out(r, counts) for r in rewards], total=total)


@router.post("/rewards", response_model=RewardOut, status_code=201)
def create_reward(
    payload: RewardCreate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    reward = Reward(**payload.model_dump())
    db.add(reward)
    db.flush()
    log_action(
        db, current.id, AuditAction.create, "reward", reward.id,
        entity_label=reward.name, after=snapshot(reward, AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(reward)
    return _reward_out(reward, {})


@router.patch("/rewards/{reward_id}", response_model=RewardOut)
def update_reward(
    reward_id: int,
    payload: RewardUpdate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    reward = db.get(Reward, reward_id)
    if reward is None:
        raise HTTPException(status_code=404, detail="Reward not found")
    before = snapshot(reward, AUDIT_FIELDS)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(reward, field, value)
    log_action(
        db, current.id, AuditAction.update, "reward", reward.id,
        entity_label=reward.name, before=before, after=snapshot(reward, AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(reward)
    return _reward_out(reward, _redeemed_counts(db, [reward.id]))


@router.delete("/rewards/{reward_id}", response_model=Msg)
def delete_reward(
    reward_id: int,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    reward = db.get(Reward, reward_id)
    if reward is None:
        raise HTTPException(status_code=404, detail="Reward not found")
    redeemed = _redeemed_counts(db, [reward.id]).get(reward.id, 0)
    if redeemed:
        raise HTTPException(
            status_code=409,
            detail="Reward has redemption history; mark it inactive instead",
        )
    before = snapshot(reward, AUDIT_FIELDS)
    db.delete(reward)
    log_action(
        db, current.id, AuditAction.delete, "reward", reward_id,
        entity_label=reward.name, before=before,
    )
    db.commit()
    return Msg(detail="Reward deleted")
