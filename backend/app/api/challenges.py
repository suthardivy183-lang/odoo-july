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
    ChallengeStatus,
    EvidenceMode,
    NotificationType,
    ParticipationStatus,
    Role,
)
from app.models.gamification import Challenge, ChallengeParticipation
from app.models.masterdata import Category
from app.schemas.challenges import (
    ChallengeCreate,
    ChallengeOut,
    ChallengeParticipationOut,
    ChallengeStatusIn,
    ChallengeUpdate,
    ProgressIn,
)
from app.schemas.common import Msg, Page
from app.schemas.csr import DecisionIn, ProofIn
from app.services.audit import log_action, snapshot
from app.services.badges import evaluate_user_badges
from app.services.notify import notify
from app.services.org import can_decide_for, managed_dept_ids
from app.services.org_settings import get_org_settings
from app.services.xp import award_once_for_challenge
from app.utils.time import now_utc

router = APIRouter(tags=["Challenges"])

CHALLENGE_AUDIT_FIELDS = [
    "title", "category_id", "xp", "difficulty", "evidence", "deadline", "status",
]
VALID_TRANSITIONS = {
    ChallengeStatus.draft: {ChallengeStatus.active, ChallengeStatus.archived},
    ChallengeStatus.active: {ChallengeStatus.under_review, ChallengeStatus.archived},
    ChallengeStatus.under_review: {ChallengeStatus.completed, ChallengeStatus.archived},
    ChallengeStatus.completed: {ChallengeStatus.archived},
    ChallengeStatus.archived: set(),
}
DECIDABLE = {
    ParticipationStatus.joined,
    ParticipationStatus.submitted,
    ParticipationStatus.resubmission_requested,
}
JOINABLE = {ChallengeStatus.active, ChallengeStatus.under_review}


def _participant_counts(db: Session, challenge_ids: list[int]) -> dict[int, int]:
    if not challenge_ids:
        return {}
    rows = db.execute(
        select(ChallengeParticipation.challenge_id, func.count(ChallengeParticipation.id))
        .where(ChallengeParticipation.challenge_id.in_(challenge_ids))
        .group_by(ChallengeParticipation.challenge_id)
    ).all()
    return {challenge_id: count for challenge_id, count in rows}


def _my_participations(
    db: Session, user_id: int, challenge_ids: list[int]
) -> dict[int, ChallengeParticipation]:
    if not challenge_ids:
        return {}
    rows = (
        db.execute(
            select(ChallengeParticipation).where(
                ChallengeParticipation.user_id == user_id,
                ChallengeParticipation.challenge_id.in_(challenge_ids),
            )
        )
        .scalars()
        .all()
    )
    return {p.challenge_id: p for p in rows}


def _challenge_out(
    challenge: Challenge,
    counts: dict[int, int],
    mine: dict[int, ChallengeParticipation],
) -> ChallengeOut:
    out = ChallengeOut.model_validate(challenge)
    out.category_name = challenge.category.name if challenge.category else None
    out.participant_count = counts.get(challenge.id, 0)
    part = mine.get(challenge.id)
    if part is not None:
        out.my_participation_id = part.id
        out.my_participation_status = part.status
        out.my_progress = part.progress
    return out


def _participation_out(part: ChallengeParticipation) -> ChallengeParticipationOut:
    out = ChallengeParticipationOut.model_validate(part)
    out.challenge_title = part.challenge.title if part.challenge else None
    out.challenge_xp = part.challenge.xp if part.challenge else None
    out.challenge_evidence = part.challenge.evidence if part.challenge else None
    out.approver = part.approver
    return out


def _get_challenge(db: Session, challenge_id: int) -> Challenge:
    challenge = db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge


def _get_participation(db: Session, participation_id: int) -> ChallengeParticipation:
    part = db.execute(
        select(ChallengeParticipation)
        .options(
            joinedload(ChallengeParticipation.challenge),
            joinedload(ChallengeParticipation.user),
            joinedload(ChallengeParticipation.proof),
            joinedload(ChallengeParticipation.approver),
        )
        .where(ChallengeParticipation.id == participation_id)
    ).scalar_one_or_none()
    if part is None:
        raise HTTPException(status_code=404, detail="Participation not found")
    return part


def _proof_required(db: Session, challenge: Challenge) -> bool:
    if challenge.evidence == EvidenceMode.required:
        return True
    if challenge.evidence == EvidenceMode.not_required:
        return False
    return get_org_settings(db).evidence_requirement


@router.get("/challenges", response_model=Page[ChallengeOut])
def list_challenges(
    status: ChallengeStatus | None = None,
    category_id: int | None = None,
    difficulty: str | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = Query(20, le=100),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Challenge)
    if current.role == Role.employee:
        stmt = stmt.where(Challenge.status != ChallengeStatus.draft)
    if status is not None:
        stmt = stmt.where(Challenge.status == status)
    if category_id is not None:
        stmt = stmt.where(Challenge.category_id == category_id)
    if difficulty:
        stmt = stmt.where(Challenge.difficulty == difficulty)
    if q:
        stmt = stmt.where(Challenge.title.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    challenges = (
        db.execute(
            stmt.options(joinedload(Challenge.category))
            .order_by(Challenge.deadline.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    ids = [c.id for c in challenges]
    counts = _participant_counts(db, ids)
    mine = _my_participations(db, current.id, ids)
    return Page[ChallengeOut](
        items=[_challenge_out(c, counts, mine) for c in challenges], total=total
    )


@router.get("/challenges/{challenge_id}", response_model=ChallengeOut)
def get_challenge(
    challenge_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    challenge = _get_challenge(db, challenge_id)
    if current.role == Role.employee and challenge.status == ChallengeStatus.draft:
        raise HTTPException(status_code=404, detail="Challenge not found")
    counts = _participant_counts(db, [challenge.id])
    mine = _my_participations(db, current.id, [challenge.id])
    return _challenge_out(challenge, counts, mine)


@router.post("/challenges", response_model=ChallengeOut, status_code=201)
def create_challenge(
    payload: ChallengeCreate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    category = db.get(Category, payload.category_id)
    if category is None or category.type != CategoryType.challenge:
        raise HTTPException(status_code=400, detail="A valid challenge category is required")
    if category.status != ActiveStatus.active:
        raise HTTPException(status_code=400, detail="Category is inactive")
    challenge = Challenge(**payload.model_dump(), created_by=current.id)
    db.add(challenge)
    db.flush()
    log_action(
        db, current.id, AuditAction.create, "challenge", challenge.id,
        entity_label=challenge.title, after=snapshot(challenge, CHALLENGE_AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(challenge)
    return _challenge_out(challenge, {}, {})


@router.patch("/challenges/{challenge_id}", response_model=ChallengeOut)
def update_challenge(
    challenge_id: int,
    payload: ChallengeUpdate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    challenge = _get_challenge(db, challenge_id)
    before = snapshot(challenge, CHALLENGE_AUDIT_FIELDS)
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        category = db.get(Category, data["category_id"])
        if category is None or category.type != CategoryType.challenge:
            raise HTTPException(status_code=400, detail="A valid challenge category is required")
    for field, value in data.items():
        setattr(challenge, field, value)
    log_action(
        db, current.id, AuditAction.update, "challenge", challenge.id,
        entity_label=challenge.title, before=before,
        after=snapshot(challenge, CHALLENGE_AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(challenge)
    counts = _participant_counts(db, [challenge.id])
    return _challenge_out(challenge, counts, _my_participations(db, current.id, [challenge.id]))


@router.post("/challenges/{challenge_id}/status", response_model=ChallengeOut)
def change_challenge_status(
    challenge_id: int,
    payload: ChallengeStatusIn,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    challenge = _get_challenge(db, challenge_id)
    if payload.status == challenge.status:
        raise HTTPException(status_code=400, detail="Challenge is already in this status")
    if payload.status not in VALID_TRANSITIONS[challenge.status]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move a {challenge.status.value} challenge to {payload.status.value}",
        )
    before = snapshot(challenge, ["status"])
    challenge.status = payload.status
    log_action(
        db, current.id, AuditAction.status_change, "challenge", challenge.id,
        entity_label=challenge.title, before=before, after=snapshot(challenge, ["status"]),
    )
    db.commit()
    db.refresh(challenge)
    counts = _participant_counts(db, [challenge.id])
    return _challenge_out(challenge, counts, _my_participations(db, current.id, [challenge.id]))


@router.delete("/challenges/{challenge_id}", response_model=Msg)
def delete_challenge(
    challenge_id: int,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    challenge = _get_challenge(db, challenge_id)
    if challenge.status != ChallengeStatus.draft:
        raise HTTPException(status_code=409, detail="Only draft challenges can be deleted; archive instead")
    if _participant_counts(db, [challenge.id]).get(challenge.id, 0):
        raise HTTPException(status_code=409, detail="Challenge already has participants")
    before = snapshot(challenge, CHALLENGE_AUDIT_FIELDS)
    db.delete(challenge)
    log_action(
        db, current.id, AuditAction.delete, "challenge", challenge_id,
        entity_label=challenge.title, before=before,
    )
    db.commit()
    return Msg(detail="Challenge deleted")


@router.post("/challenges/{challenge_id}/join", response_model=ChallengeParticipationOut, status_code=201)
def join_challenge(
    challenge_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    challenge = _get_challenge(db, challenge_id)
    if challenge.status not in JOINABLE:
        raise HTTPException(status_code=400, detail="Only active challenges can be joined")
    existing = db.execute(
        select(ChallengeParticipation).where(
            ChallengeParticipation.challenge_id == challenge.id,
            ChallengeParticipation.user_id == current.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already joined this challenge")
    part = ChallengeParticipation(challenge_id=challenge.id, user_id=current.id)
    db.add(part)
    db.flush()
    log_action(
        db, current.id, AuditAction.create, "challenge_participation", part.id,
        entity_label=f"{current.full_name} joined {challenge.title}",
    )
    db.commit()
    return _participation_out(_get_participation(db, part.id))


@router.post("/challenges/participations/{participation_id}/progress", response_model=ChallengeParticipationOut)
def update_progress(
    participation_id: int,
    payload: ProgressIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    part = _get_participation(db, participation_id)
    is_owner = part.user_id == current.id
    if not is_owner and not can_decide_for(db, current, part.user):
        raise HTTPException(status_code=403, detail="You cannot update this participant's progress")
    if part.status == ParticipationStatus.approved:
        raise HTTPException(status_code=400, detail="Participation is already approved")
    before = snapshot(part, ["progress"])
    part.progress = payload.progress
    log_action(
        db, current.id, AuditAction.update, "challenge_participation", part.id,
        entity_label=f"{part.user.full_name} — {part.challenge.title}",
        before=before, after=snapshot(part, ["progress"]),
    )
    db.commit()
    return _participation_out(_get_participation(db, part.id))


@router.post("/challenges/participations/{participation_id}/proof", response_model=ChallengeParticipationOut)
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
    attachment.entity_type = "challenge_participation"
    attachment.entity_id = part.id
    challenge = part.challenge
    if challenge.status == ChallengeStatus.active:
        challenge.status = ChallengeStatus.under_review
        log_action(
            db, current.id, AuditAction.status_change, "challenge", challenge.id,
            entity_label=challenge.title,
            before={"status": ChallengeStatus.active.value},
            after={"status": ChallengeStatus.under_review.value},
        )
    log_action(
        db, current.id, AuditAction.update, "challenge_participation", part.id,
        entity_label=challenge.title, before=before,
        after=snapshot(part, ["status", "proof_attachment_id"]),
    )
    db.commit()
    return _participation_out(_get_participation(db, part.id))


@router.post("/challenges/participations/{participation_id}/decision", response_model=ChallengeParticipationOut)
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
        raise HTTPException(status_code=400, detail=f"Participation is already {part.status.value}")
    if payload.decision == "approve":
        if _proof_required(db, part.challenge) and part.proof_attachment_id is None:
            raise HTTPException(
                status_code=400,
                detail="Evidence is required: participation cannot be approved without proof",
            )
        part.status = ParticipationStatus.approved
        action = AuditAction.approve
        title = f"Challenge approved: {part.challenge.title}"
    elif payload.decision == "reject":
        part.status = ParticipationStatus.rejected
        action = AuditAction.reject
        title = f"Challenge submission rejected: {part.challenge.title}"
    else:
        part.status = ParticipationStatus.resubmission_requested
        action = AuditAction.resubmission_request
        title = f"Resubmission requested: {part.challenge.title}"
    part.decided_by = current.id
    part.decided_at = now_utc()
    part.approver_comment = payload.comment.strip() or None

    if payload.decision == "approve":
        award_once_for_challenge(db, part.id, current.id)
        evaluate_user_badges(db, part.user)
    notify(
        db, part.user, NotificationType.challenge_decision, title,
        body=payload.comment.strip() or title,
        entity_type="challenge_participation", entity_id=part.id,
    )
    log_action(
        db, current.id, action, "challenge_participation", part.id,
        entity_label=f"{part.user.full_name} — {part.challenge.title}",
        after={"status": part.status.value, "comment": part.approver_comment},
    )
    db.commit()
    return _participation_out(_get_participation(db, part.id))


@router.get("/challenges/participations/inbox", response_model=Page[ChallengeParticipationOut])
def list_participations(
    challenge_id: int | None = None,
    status: ParticipationStatus | None = None,
    department_id: int | None = None,
    page: int = 1,
    size: int = Query(20, le=100),
    current: User = Depends(require_head),
    db: Session = Depends(get_db),
):
    stmt = select(ChallengeParticipation).join(User, ChallengeParticipation.user_id == User.id)
    if current.role == Role.dept_head:
        scope = managed_dept_ids(db, current)
        if not scope:
            return Page[ChallengeParticipationOut](items=[], total=0)
        stmt = stmt.where(User.department_id.in_(scope))
    if challenge_id is not None:
        stmt = stmt.where(ChallengeParticipation.challenge_id == challenge_id)
    if status is not None:
        stmt = stmt.where(ChallengeParticipation.status == status)
    if department_id is not None:
        stmt = stmt.where(User.department_id == department_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.options(
                joinedload(ChallengeParticipation.challenge),
                joinedload(ChallengeParticipation.user),
                joinedload(ChallengeParticipation.proof),
                joinedload(ChallengeParticipation.approver),
            )
            .order_by(ChallengeParticipation.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return Page[ChallengeParticipationOut](
        items=[_participation_out(p) for p in rows], total=total
    )


@router.get("/challenges/participations/me", response_model=list[ChallengeParticipationOut])
def my_participations(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            select(ChallengeParticipation)
            .options(
                joinedload(ChallengeParticipation.challenge),
                joinedload(ChallengeParticipation.user),
                joinedload(ChallengeParticipation.proof),
                joinedload(ChallengeParticipation.approver),
            )
            .where(ChallengeParticipation.user_id == current.id)
            .order_by(ChallengeParticipation.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_participation_out(p) for p in rows]
