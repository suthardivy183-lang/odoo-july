import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_head
from app.db.session import get_db
from app.models.core import Department, Notification, User
from app.models.enums import (
    ChallengeStatus,
    CSRStatus,
    ParticipationStatus,
    PolicyStatus,
    Role,
)
from app.models.gamification import Challenge, ChallengeParticipation, XPTransaction
from app.models.masterdata import ESGPolicy, PolicyAcknowledgement, UserBadge
from app.models.social import CSRActivity, CSRParticipation
from app.schemas.common import UserBrief
from app.schemas.dashboards import (
    EmployeeDashboardOut,
    GenderSlice,
    HeadDashboardOut,
    MonthlyEngagement,
    TopPerformer,
)
from app.services.org import descendant_dept_ids, managed_dept_ids
from app.services.xp import (
    approved_challenge_count,
    approved_csr_count,
    lifetime_earned_xp,
)
from app.utils.time import today_ist

router = APIRouter(tags=["Dashboards"])

PENDING = (ParticipationStatus.submitted, ParticipationStatus.resubmission_requested)


def _all_time_rank(db: Session, user_id: int) -> int | None:
    rows = db.execute(
        select(XPTransaction.user_id, func.sum(XPTransaction.amount).label("xp"))
        .join(User, XPTransaction.user_id == User.id)
        .where(XPTransaction.amount > 0, User.is_active.is_(True))
        .group_by(XPTransaction.user_id)
        .order_by(func.sum(XPTransaction.amount).desc())
    ).all()
    rank = 0
    prev: int | None = None
    for position, (uid, xp) in enumerate(rows, start=1):
        if xp != prev:
            rank = position
            prev = xp
        if uid == user_id:
            return rank
    return None


@router.get("/dashboards/employee", response_model=EmployeeDashboardOut)
def employee_dashboard(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    badges = db.execute(
        select(func.count(UserBadge.id)).where(UserBadge.user_id == current.id)
    ).scalar_one()
    active_parts = db.execute(
        select(func.count(ChallengeParticipation.id)).where(
            ChallengeParticipation.user_id == current.id,
            ChallengeParticipation.status.in_(
                [
                    ParticipationStatus.joined,
                    ParticipationStatus.submitted,
                    ParticipationStatus.resubmission_requested,
                ]
            ),
        )
    ).scalar_one()
    csr_parts = db.execute(
        select(func.count(CSRParticipation.id)).where(CSRParticipation.user_id == current.id)
    ).scalar_one()
    published = db.execute(
        select(ESGPolicy.id, ESGPolicy.version).where(ESGPolicy.status == PolicyStatus.published)
    ).all()
    acked = set(
        db.execute(
            select(PolicyAcknowledgement.policy_id, PolicyAcknowledgement.policy_version).where(
                PolicyAcknowledgement.user_id == current.id
            )
        ).all()
    )
    pending_acks = sum(1 for pid, version in published if (pid, version) not in acked)
    unread = db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current.id, Notification.is_read.is_(False)
        )
    ).scalar_one()
    open_challenges = db.execute(
        select(func.count(Challenge.id)).where(Challenge.status == ChallengeStatus.active)
    ).scalar_one()
    open_csr = db.execute(
        select(func.count(CSRActivity.id)).where(CSRActivity.status == CSRStatus.active)
    ).scalar_one()
    return EmployeeDashboardOut(
        xp_balance=current.xp_balance,
        lifetime_earned=lifetime_earned_xp(db, current.id),
        my_rank=_all_time_rank(db, current.id),
        badges_count=badges,
        active_challenge_participations=active_parts,
        approved_challenges=approved_challenge_count(db, current.id),
        csr_participations=csr_parts,
        approved_csr=approved_csr_count(db, current.id),
        pending_policy_acks=pending_acks,
        unread_notifications=unread,
        active_challenges_open=open_challenges,
        active_csr_open=open_csr,
    )


@router.get("/dashboards/head", response_model=HeadDashboardOut)
def head_dashboard(
    department_id: int | None = None,
    current: User = Depends(require_head),
    db: Session = Depends(get_db),
):
    if current.role == Role.dept_head:
        scope = managed_dept_ids(db, current)
        if department_id is not None:
            if department_id not in scope:
                raise HTTPException(status_code=403, detail="Department outside your scope")
            scope = descendant_dept_ids(db, department_id)
    else:  # esg_manager / admin
        if department_id is not None:
            if db.get(Department, department_id) is None:
                raise HTTPException(status_code=404, detail="Department not found")
            scope = descendant_dept_ids(db, department_id)
        else:
            scope = {d for (d,) in db.execute(select(Department.id)).all()}
    scope_list = sorted(scope)
    if not scope_list:
        return HeadDashboardOut(
            department_ids=[], headcount=0, pending_csr_approvals=0,
            pending_challenge_approvals=0, csr_participation_rate=0,
            challenge_completion_rate=0, gender_distribution=[],
            engagement_trend=[], top_performers=[], as_of=today_ist(),
        )

    in_scope = User.department_id.in_(scope_list)
    headcount = db.execute(
        select(func.count(User.id)).where(in_scope, User.is_active.is_(True))
    ).scalar_one()

    pending_csr = db.execute(
        select(func.count(CSRParticipation.id))
        .join(User, CSRParticipation.user_id == User.id)
        .where(in_scope, CSRParticipation.status.in_(PENDING))
    ).scalar_one()
    pending_challenge = db.execute(
        select(func.count(ChallengeParticipation.id))
        .join(User, ChallengeParticipation.user_id == User.id)
        .where(in_scope, ChallengeParticipation.status.in_(PENDING))
    ).scalar_one()

    csr_participants = db.execute(
        select(func.count(func.distinct(CSRParticipation.user_id)))
        .join(User, CSRParticipation.user_id == User.id)
        .where(in_scope, CSRParticipation.status == ParticipationStatus.approved)
    ).scalar_one()
    challenge_completers = db.execute(
        select(func.count(func.distinct(ChallengeParticipation.user_id)))
        .join(User, ChallengeParticipation.user_id == User.id)
        .where(in_scope, ChallengeParticipation.status == ParticipationStatus.approved)
    ).scalar_one()

    genders = db.execute(
        select(User.gender, func.count(User.id))
        .where(in_scope, User.is_active.is_(True))
        .group_by(User.gender)
    ).all()

    # participations per month, last 6 IST months
    today = today_ist()
    months: list[tuple[int, int]] = []
    year, month = today.year, today.month
    for _ in range(6):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    months.reverse()
    month_start = dt.date(months[0][0], months[0][1], 1)

    csr_rows = db.execute(
        select(CSRParticipation.created_at)
        .join(User, CSRParticipation.user_id == User.id)
        .where(in_scope, CSRParticipation.created_at >= month_start)
    ).all()
    ch_rows = db.execute(
        select(ChallengeParticipation.created_at)
        .join(User, ChallengeParticipation.user_id == User.id)
        .where(in_scope, ChallengeParticipation.created_at >= month_start)
    ).all()
    trend = {f"{y:04d}-{m:02d}": {"csr": 0, "challenges": 0} for y, m in months}
    for (created,) in csr_rows:
        key = f"{created.year:04d}-{created.month:02d}"
        if key in trend:
            trend[key]["csr"] += 1
    for (created,) in ch_rows:
        key = f"{created.year:04d}-{created.month:02d}"
        if key in trend:
            trend[key]["challenges"] += 1

    dept_names = {d.id: d.name for d in db.execute(select(Department)).scalars().all()}
    top = (
        db.execute(
            select(User)
            .where(in_scope, User.is_active.is_(True))
            .order_by(User.xp_balance.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )

    def pct(n: int) -> float:
        return round(n * 100 / headcount, 1) if headcount else 0.0

    return HeadDashboardOut(
        department_ids=scope_list,
        headcount=headcount,
        pending_csr_approvals=pending_csr,
        pending_challenge_approvals=pending_challenge,
        csr_participation_rate=pct(csr_participants),
        challenge_completion_rate=pct(challenge_completers),
        gender_distribution=[
            GenderSlice(gender=g.value, count=c) for g, c in genders
        ],
        engagement_trend=[
            MonthlyEngagement(month=k, csr=v["csr"], challenges=v["challenges"])
            for k, v in trend.items()
        ],
        top_performers=[
            TopPerformer(
                user=UserBrief.model_validate(u),
                department_name=dept_names.get(u.department_id),
                xp_balance=u.xp_balance,
            )
            for u in top
        ],
        as_of=today_ist(),
    )
