from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_admin, require_esg
from app.db.session import get_db
from app.models.core import User
from app.models.enums import ActiveStatus, AuditAction, BadgeRule
from app.models.masterdata import Badge, UserBadge
from app.schemas.badges import (
    BadgeAwardIn,
    BadgeCreate,
    BadgeHolderOut,
    BadgeOut,
    BadgeUpdate,
    UserBadgeOut,
)
from app.schemas.common import Msg, Page
from app.services.audit import log_action, snapshot
from app.services.badges import assign_badge_manual, sweep_all

router = APIRouter(tags=["Badges"])

AUDIT_FIELDS = ["name", "description", "icon", "rule_type", "rule_value", "status"]


def _holders_counts(db: Session, badge_ids: list[int]) -> dict[int, int]:
    if not badge_ids:
        return {}
    rows = db.execute(
        select(UserBadge.badge_id, func.count(UserBadge.id))
        .where(UserBadge.badge_id.in_(badge_ids))
        .group_by(UserBadge.badge_id)
    ).all()
    return {badge_id: count for badge_id, count in rows}


def _badge_out(badge: Badge, holders: dict[int, int]) -> BadgeOut:
    out = BadgeOut.model_validate(badge)
    out.holders_count = holders.get(badge.id, 0)
    return out


@router.get("/badges", response_model=Page[BadgeOut])
def list_badges(
    status: ActiveStatus | None = None,
    rule_type: BadgeRule | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = Query(50, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Badge)
    if status is not None:
        stmt = stmt.where(Badge.status == status)
    if rule_type is not None:
        stmt = stmt.where(Badge.rule_type == rule_type)
    if q:
        stmt = stmt.where(Badge.name.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    badges = (
        db.execute(stmt.order_by(Badge.created_at.desc()).offset((page - 1) * size).limit(size))
        .scalars()
        .all()
    )
    holders = _holders_counts(db, [b.id for b in badges])
    return Page[BadgeOut](items=[_badge_out(b, holders) for b in badges], total=total)


@router.get("/badges/me", response_model=list[UserBadgeOut])
def my_badges(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(UserBadge)
            .options(joinedload(UserBadge.badge))
            .where(UserBadge.user_id == current.id)
            .order_by(UserBadge.awarded_at.desc())
        )
        .scalars()
        .all()
    )
    holders = _holders_counts(db, [r.badge_id for r in rows])
    return [
        UserBadgeOut(
            id=r.id,
            badge=_badge_out(r.badge, holders),
            awarded_at=r.awarded_at,
            awarded_by=r.awarded_by,
        )
        for r in rows
    ]


@router.post("/badges", response_model=BadgeOut, status_code=201)
def create_badge(
    payload: BadgeCreate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    dup = db.execute(select(Badge).where(Badge.name == payload.name)).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(status_code=409, detail="A badge with this name already exists")
    badge = Badge(**payload.model_dump())
    db.add(badge)
    db.flush()
    log_action(
        db, current.id, AuditAction.create, "badge", badge.id,
        entity_label=badge.name, after=snapshot(badge, AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(badge)
    return _badge_out(badge, {})


@router.patch("/badges/{badge_id}", response_model=BadgeOut)
def update_badge(
    badge_id: int,
    payload: BadgeUpdate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    badge = db.get(Badge, badge_id)
    if badge is None:
        raise HTTPException(status_code=404, detail="Badge not found")
    before = snapshot(badge, AUDIT_FIELDS)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != badge.name:
        dup = db.execute(
            select(Badge).where(Badge.name == data["name"], Badge.id != badge.id)
        ).scalar_one_or_none()
        if dup is not None:
            raise HTTPException(status_code=409, detail="A badge with this name already exists")
    for field, value in data.items():
        setattr(badge, field, value)
    if badge.rule_type == BadgeRule.manual:
        badge.rule_value = None
    elif badge.rule_value is None:
        raise HTTPException(status_code=400, detail="Automatic badges require a rule value")
    log_action(
        db, current.id, AuditAction.update, "badge", badge.id,
        entity_label=badge.name, before=before, after=snapshot(badge, AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(badge)
    return _badge_out(badge, _holders_counts(db, [badge.id]))


@router.delete("/badges/{badge_id}", response_model=Msg)
def delete_badge(
    badge_id: int,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    badge = db.get(Badge, badge_id)
    if badge is None:
        raise HTTPException(status_code=404, detail="Badge not found")
    holders = _holders_counts(db, [badge.id]).get(badge.id, 0)
    if holders:
        raise HTTPException(
            status_code=409,
            detail="Badge has already been awarded to employees; mark it inactive instead",
        )
    before = snapshot(badge, AUDIT_FIELDS)
    db.delete(badge)
    log_action(
        db, current.id, AuditAction.delete, "badge", badge_id,
        entity_label=badge.name, before=before,
    )
    db.commit()
    return Msg(detail="Badge deleted")


@router.get("/badges/{badge_id}/holders", response_model=Page[BadgeHolderOut])
def badge_holders(
    badge_id: int,
    page: int = 1,
    size: int = Query(20, le=100),
    _: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    badge = db.get(Badge, badge_id)
    if badge is None:
        raise HTTPException(status_code=404, detail="Badge not found")
    stmt = select(UserBadge).where(UserBadge.badge_id == badge_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.options(joinedload(UserBadge.user))
            .order_by(UserBadge.awarded_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return Page[BadgeHolderOut](items=rows, total=total)


@router.post("/badges/{badge_id}/award", response_model=Msg)
def award_badge_manually(
    badge_id: int,
    payload: BadgeAwardIn,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    badge = db.get(Badge, badge_id)
    if badge is None:
        raise HTTPException(status_code=404, detail="Badge not found")
    if badge.status != ActiveStatus.active:
        raise HTTPException(status_code=400, detail="Badge is inactive")
    user = db.get(User, payload.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="Employee not found or inactive")
    granted = assign_badge_manual(db, user, badge, actor_id=current.id)
    if granted is None:
        raise HTTPException(status_code=409, detail="Employee already holds this badge")
    db.commit()
    return Msg(detail=f"Badge '{badge.name}' awarded to {user.full_name}")


@router.post("/badges/sweep", response_model=Msg)
def run_badge_sweep(
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    count = sweep_all(db)
    db.commit()
    return Msg(detail=f"Badge sweep complete: {count} badge(s) awarded")
