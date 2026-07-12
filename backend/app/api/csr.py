import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_esg, require_head
from app.db.session import get_db
from app.models.core import Attachment, User
from app.models.enums import (
    ActiveStatus,
    AuditAction,
    CategoryType,
    CSRStatus,
    NotificationType,
    ParticipationStatus,
    Role,
)
from app.models.masterdata import Category
from app.models.social import CSRActivity, CSRParticipation
from app.schemas.common import Msg, Page
from app.schemas.csr import (
    CSRActivityCreate,
    CSRActivityOut,
    CSRActivityUpdate,
    CSRParticipationOut,
    CSRStatusIn,
    DecisionIn,
    ProofIn,
)
from app.services.audit import log_action, snapshot
from app.services.badges import evaluate_user_badges
from app.services.notify import notify
from app.services.org import can_decide_for, managed_dept_ids
from app.services.org_settings import get_org_settings
from app.services.xp import award_once_for_csr
from app.utils.time import now_utc

router = APIRouter(tags=["CSR"])

ACTIVITY_AUDIT_FIELDS = [
    "title", "category_id", "location", "organizer_user_id", "capacity",
    "start_date", "end_date", "budget_inr", "points", "status",
]
VALID_TRANSITIONS = {
    CSRStatus.draft: {CSRStatus.active, CSRStatus.archived},
    CSRStatus.active: {CSRStatus.completed, CSRStatus.archived},
    CSRStatus.completed: {CSRStatus.archived},
    CSRStatus.archived: set(),
}
DECIDABLE = {
    ParticipationStatus.joined,
    ParticipationStatus.submitted,
    ParticipationStatus.resubmission_requested,
}


def _joined_counts(db: Session, activity_ids: list[int]) -> dict[int, int]:
    if not activity_ids:
        return {}
    rows = db.execute(
        select(CSRParticipation.activity_id, func.count(CSRParticipation.id))
        .where(CSRParticipation.activity_id.in_(activity_ids))
        .group_by(CSRParticipation.activity_id)
    ).all()
    return {activity_id: count for activity_id, count in rows}


def _activity_out(
    activity: CSRActivity,
    counts: dict[int, int],
    mine: dict[int, CSRParticipation],
) -> CSRActivityOut:
    out = CSRActivityOut.model_validate(activity)
    out.category_name = activity.category.name if activity.category else None
    out.organizer = activity.organizer
    out.joined_count = counts.get(activity.id, 0)
    part = mine.get(activity.id)
    if part is not None:
        out.my_participation_id = part.id
        out.my_participation_status = part.status
    return out


def _my_participations(
    db: Session, user_id: int, activity_ids: list[int]
) -> dict[int, CSRParticipation]:
    if not activity_ids:
        return {}
    rows = (
        db.execute(
            select(CSRParticipation).where(
                CSRParticipation.user_id == user_id,
                CSRParticipation.activity_id.in_(activity_ids),
            )
        )
        .scalars()
        .all()
    )
    return {p.activity_id: p for p in rows}


def _participation_out(part: CSRParticipation) -> CSRParticipationOut:
    out = CSRParticipationOut.model_validate(part)
    out.activity_title = part.activity.title if part.activity else None
    out.activity_points = part.activity.points if part.activity else None
    out.approver = part.approver
    return out


def _get_activity(db: Session, activity_id: int) -> CSRActivity:
    activity = db.get(CSRActivity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="CSR activity not found")
    return activity


def _get_participation(db: Session, participation_id: int) -> CSRParticipation:
    part = db.execute(
        select(CSRParticipation)
        .options(
            joinedload(CSRParticipation.activity),
            joinedload(CSRParticipation.user),
            joinedload(CSRParticipation.proof),
        )
        .where(CSRParticipation.id == participation_id)
    ).scalar_one_or_none()
    if part is None:
        raise HTTPException(status_code=404, detail="Participation not found")
    return part


@router.get("/csr/activities", response_model=Page[CSRActivityOut])
def list_activities(
    status: CSRStatus | None = None,
    category_id: int | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = Query(20, le=100),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(CSRActivity)
    if current.role == Role.employee:
        stmt = stmt.where(CSRActivity.status.in_([CSRStatus.active, CSRStatus.completed]))
    if status is not None:
        stmt = stmt.where(CSRActivity.status == status)
    if category_id is not None:
        stmt = stmt.where(CSRActivity.category_id == category_id)
    if q:
        stmt = stmt.where(CSRActivity.title.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    activities = (
        db.execute(
            stmt.options(joinedload(CSRActivity.category), joinedload(CSRActivity.organizer))
            .order_by(CSRActivity.start_date.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    ids = [a.id for a in activities]
    counts = _joined_counts(db, ids)
    mine = _my_participations(db, current.id, ids)
    return Page[CSRActivityOut](
        items=[_activity_out(a, counts, mine) for a in activities], total=total
    )


@router.get("/csr/activities/{activity_id}", response_model=CSRActivityOut)
def get_activity(
    activity_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activity = _get_activity(db, activity_id)
    if current.role == Role.employee and activity.status in (CSRStatus.draft,):
        raise HTTPException(status_code=404, detail="CSR activity not found")
    counts = _joined_counts(db, [activity.id])
    mine = _my_participations(db, current.id, [activity.id])
    return _activity_out(activity, counts, mine)


@router.post("/csr/activities", response_model=CSRActivityOut, status_code=201)
def create_activity(
    payload: CSRActivityCreate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    category = db.get(Category, payload.category_id)
    if category is None or category.type != CategoryType.csr:
        raise HTTPException(status_code=400, detail="A valid CSR category is required")
    if category.status != ActiveStatus.active:
        raise HTTPException(status_code=400, detail="Category is inactive")
    if payload.organizer_user_id is not None and db.get(User, payload.organizer_user_id) is None:
        raise HTTPException(status_code=400, detail="Organizer user does not exist")
    activity = CSRActivity(**payload.model_dump(), created_by=current.id)
    db.add(activity)
    db.flush()
    log_action(
        db, current.id, AuditAction.create, "csr_activity", activity.id,
        entity_label=activity.title, after=snapshot(activity, ACTIVITY_AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(activity)
    return _activity_out(activity, {}, {})


@router.patch("/csr/activities/{activity_id}", response_model=CSRActivityOut)
def update_activity(
    activity_id: int,
    payload: CSRActivityUpdate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    activity = _get_activity(db, activity_id)
    before = snapshot(activity, ACTIVITY_AUDIT_FIELDS)
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        category = db.get(Category, data["category_id"])
        if category is None or category.type != CategoryType.csr:
            raise HTTPException(status_code=400, detail="A valid CSR category is required")
    if "organizer_user_id" in data and data["organizer_user_id"] is not None:
        if db.get(User, data["organizer_user_id"]) is None:
            raise HTTPException(status_code=400, detail="Organizer user does not exist")
    for field, value in data.items():
        setattr(activity, field, value)
    if activity.end_date < activity.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")
    log_action(
        db, current.id, AuditAction.update, "csr_activity", activity.id,
        entity_label=activity.title, before=before,
        after=snapshot(activity, ACTIVITY_AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(activity)
    counts = _joined_counts(db, [activity.id])
    return _activity_out(activity, counts, _my_participations(db, current.id, [activity.id]))


@router.post("/csr/activities/{activity_id}/status", response_model=CSRActivityOut)
def change_activity_status(
    activity_id: int,
    payload: CSRStatusIn,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    activity = _get_activity(db, activity_id)
    if payload.status == activity.status:
        raise HTTPException(status_code=400, detail="Activity is already in this status")
    if payload.status not in VALID_TRANSITIONS[activity.status]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move a {activity.status.value} activity to {payload.status.value}",
        )
    before = snapshot(activity, ["status"])
    activity.status = payload.status
    log_action(
        db, current.id, AuditAction.status_change, "csr_activity", activity.id,
        entity_label=activity.title, before=before, after=snapshot(activity, ["status"]),
    )
    db.commit()
    db.refresh(activity)
    counts = _joined_counts(db, [activity.id])
    return _activity_out(activity, counts, _my_participations(db, current.id, [activity.id]))


@router.delete("/csr/activities/{activity_id}", response_model=Msg)
def delete_activity(
    activity_id: int,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    activity = _get_activity(db, activity_id)
    if activity.status != CSRStatus.draft:
        raise HTTPException(status_code=409, detail="Only draft activities can be deleted; archive instead")
    if _joined_counts(db, [activity.id]).get(activity.id, 0):
        raise HTTPException(status_code=409, detail="Activity already has participants")
    before = snapshot(activity, ACTIVITY_AUDIT_FIELDS)
    db.delete(activity)
    log_action(
        db, current.id, AuditAction.delete, "csr_activity", activity_id,
        entity_label=activity.title, before=before,
    )
    db.commit()
    return Msg(detail="CSR activity deleted")


@router.post("/csr/activities/{activity_id}/join", response_model=CSRParticipationOut, status_code=201)
def join_activity(
    activity_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activity = _get_activity(db, activity_id)
    if activity.status != CSRStatus.active:
        raise HTTPException(status_code=400, detail="Only active activities can be joined")
    existing = db.execute(
        select(CSRParticipation).where(
            CSRParticipation.activity_id == activity.id,
            CSRParticipation.user_id == current.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already joined this activity")
    joined = _joined_counts(db, [activity.id]).get(activity.id, 0)
    if joined >= activity.capacity:
        raise HTTPException(status_code=400, detail="This activity is at full capacity")
    part = CSRParticipation(activity_id=activity.id, user_id=current.id)
    db.add(part)
    db.flush()
    log_action(
        db, current.id, AuditAction.create, "csr_participation", part.id,
        entity_label=f"{current.full_name} joined {activity.title}",
    )
    db.commit()
    return _participation_out(_get_participation(db, part.id))


@router.post("/csr/participations/{participation_id}/proof", response_model=CSRParticipationOut)
def submit_proof(
    participation_id: int,
    payload: ProofIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    part = _get_participation(db, participation_id)
    if part.user_id != current.id:
        raise HTTPException(status_code=403, detail="You can only submit proof for your own participation")
    if part.status == ParticipationStatus.approved:
        raise HTTPException(status_code=400, detail="Participation is already approved")
    attachment = db.get(Attachment, payload.attachment_id)
    if attachment is None or attachment.uploaded_by != current.id:
        raise HTTPException(status_code=400, detail="Attachment not found or not uploaded by you")
    before = snapshot(part, ["status", "proof_attachment_id"])
    part.proof_attachment_id = attachment.id
    part.status = ParticipationStatus.submitted
    attachment.entity_type = "csr_participation"
    attachment.entity_id = part.id
    log_action(
        db, current.id, AuditAction.update, "csr_participation", part.id,
        entity_label=part.activity.title, before=before,
        after=snapshot(part, ["status", "proof_attachment_id"]),
    )
    db.commit()
    return _participation_out(_get_participation(db, part.id))


@router.post("/csr/participations/{participation_id}/decision", response_model=CSRParticipationOut)
def decide_participation(
    participation_id: int,
    payload: DecisionIn,
    current: User = Depends(require_head),
    db: Session = Depends(get_db),
):
    part = _get_participation(db, participation_id)
    if not can_decide_for(db, current, part.user):
        raise HTTPException(status_code=403, detail="You cannot decide for this employee")
    if part.status not in DECIDABLE:
        raise HTTPException(
            status_code=400, detail=f"Participation is already {part.status.value}"
        )
    if payload.decision == "approve":
        if get_org_settings(db).evidence_requirement and part.proof_attachment_id is None:
            raise HTTPException(
                status_code=400,
                detail="Evidence is required: participation cannot be approved without proof",
            )
        part.status = ParticipationStatus.approved
        action = AuditAction.approve
        title = f"CSR participation approved: {part.activity.title}"
    elif payload.decision == "reject":
        part.status = ParticipationStatus.rejected
        action = AuditAction.reject
        title = f"CSR participation rejected: {part.activity.title}"
    else:
        part.status = ParticipationStatus.resubmission_requested
        action = AuditAction.resubmission_request
        title = f"Resubmission requested: {part.activity.title}"
    part.decided_by = current.id
    part.decided_at = now_utc()
    part.approver_comment = payload.comment.strip() or None

    if payload.decision == "approve":
        award_once_for_csr(db, part.id, current.id)
        evaluate_user_badges(db, part.user)
    notify(
        db, part.user, NotificationType.csr_decision, title,
        body=payload.comment.strip() or title,
        entity_type="csr_participation", entity_id=part.id,
    )
    log_action(
        db, current.id, action, "csr_participation", part.id,
        entity_label=f"{part.user.full_name} — {part.activity.title}",
        after={"status": part.status.value, "comment": part.approver_comment},
    )
    db.commit()
    return _participation_out(_get_participation(db, part.id))


@router.get("/csr/participations", response_model=Page[CSRParticipationOut])
def list_participations(
    activity_id: int | None = None,
    status: ParticipationStatus | None = None,
    department_id: int | None = None,
    page: int = 1,
    size: int = Query(20, le=100),
    current: User = Depends(require_head),
    db: Session = Depends(get_db),
):
    stmt = select(CSRParticipation).join(User, CSRParticipation.user_id == User.id)
    if current.role == Role.dept_head:
        scope = managed_dept_ids(db, current)
        if not scope:
            return Page[CSRParticipationOut](items=[], total=0)
        stmt = stmt.where(User.department_id.in_(scope))
    if activity_id is not None:
        stmt = stmt.where(CSRParticipation.activity_id == activity_id)
    if status is not None:
        stmt = stmt.where(CSRParticipation.status == status)
    if department_id is not None:
        stmt = stmt.where(User.department_id == department_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.options(
                joinedload(CSRParticipation.activity),
                joinedload(CSRParticipation.user),
                joinedload(CSRParticipation.proof),
                joinedload(CSRParticipation.approver),
            )
            .order_by(CSRParticipation.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return Page[CSRParticipationOut](items=[_participation_out(p) for p in rows], total=total)


@router.get("/csr/me", response_model=list[CSRParticipationOut])
def my_participations(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            select(CSRParticipation)
            .options(
                joinedload(CSRParticipation.activity),
                joinedload(CSRParticipation.user),
                joinedload(CSRParticipation.proof),
                joinedload(CSRParticipation.approver),
            )
            .where(CSRParticipation.user_id == current.id)
            .order_by(CSRParticipation.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_participation_out(p) for p in rows]
