"""ESG scoring engine.

Implements the scoring spec (TEAM_PLAN §5). Every component is 0-100; a
component with **no data** is excluded from its pillar mean (never counted as
zero); a pillar with no present components is ``None`` and the department total
re-normalizes over the available pillar weights. The organization score is the
active-employee-count-weighted mean of department totals.

The heavy lifting (``compute_all_departments``) runs as a single pass over the
org because Environmental's *emission performance* component needs a min-max
normalization of per-employee emissions **across** departments.

The pure aggregation helpers (``pillar_mean``, ``weighted_total``) hold the
renormalization rules and are unit-tested directly.
"""

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.core import Department, User
from app.models.enums import (
    AuditStatus,
    Gender,
    GoalStatus,
    IssueStatus,
    ParticipationStatus,
    PolicyStatus,
    TrainingStatus,
)
from app.models.environment import CarbonTransaction
from app.models.governance import Audit, ComplianceIssue
from app.models.masterdata import (
    EnvironmentalGoal,
    ESGPolicy,
    PolicyAcknowledgement,
    Training,
    TrainingCompletion,
)
from app.models.scores import DepartmentScoreSnapshot, OrgScoreSnapshot
from app.models.social import CSRParticipation
from app.services.org_settings import get_org_settings
from app.utils.time import resolve_period, today_ist

# --- component metadata (key -> pillar, human label) ---

PILLAR_COMPONENTS: dict[str, list[tuple[str, str]]] = {
    "environmental": [
        ("goal_completion", "Goal completion"),
        ("emission_performance", "Emission performance"),
    ],
    "social": [
        ("csr_participation", "CSR participation"),
        ("diversity_balance", "Diversity balance"),
        ("training_completion", "Training completion"),
    ],
    "governance": [
        ("policy_ack", "Policy acknowledgement"),
        ("audit_score", "Audit performance"),
        ("compliance_health", "Compliance health"),
    ],
}


@dataclass
class Component:
    key: str
    label: str
    value: float | None  # None => no data for the period (excluded)
    inputs: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "value": None if self.value is None else round(self.value, 1),
            "inputs": self.inputs,
        }


@dataclass
class DeptScore:
    department_id: int
    department_name: str
    employee_count: int
    environmental: float | None
    social: float | None
    governance: float | None
    total: float
    components: list[Component]

    def as_dict(self) -> dict:
        return {
            "department_id": self.department_id,
            "department_name": self.department_name,
            "employee_count": self.employee_count,
            "environmental": _r(self.environmental),
            "social": _r(self.social),
            "governance": _r(self.governance),
            "total": _r(self.total),
            "components": [c.as_dict() for c in self.components],
        }


@dataclass
class OrgScore:
    environmental: float | None
    social: float | None
    governance: float | None
    total: float
    dept_count: int
    departments: list[DeptScore]

    def as_dict(self) -> dict:
        return {
            "environmental": _r(self.environmental),
            "social": _r(self.social),
            "governance": _r(self.governance),
            "total": _r(self.total),
            "dept_count": self.dept_count,
            "departments": [d.as_dict() for d in self.departments],
        }


def _r(value: float | None) -> float | None:
    return None if value is None else round(float(value), 1)


# --- pure aggregation core (unit-tested directly) ---


def pillar_mean(values: list[float | None]) -> float | None:
    """Mean of present (non-None) components; None if the pillar has none."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def weighted_total(
    environmental: float | None,
    social: float | None,
    governance: float | None,
    weights: dict[str, float],
) -> float:
    """Σ(pillar × weight) renormalized over the pillars that have data.

    A pillar scored ``None`` drops out and its weight is removed from the
    denominator, so the total is always on a 0-100 scale over whatever data
    exists. Returns 0.0 when no pillar has data.
    """
    pairs = [
        (environmental, weights["environmental"]),
        (social, weights["social"]),
        (governance, weights["governance"]),
    ]
    present = [(v, w) for v, w in pairs if v is not None]
    denom = sum(w for _, w in present)
    if denom == 0:
        return 0.0
    return sum(v * w for v, w in present) / denom


def _weights(db: Session) -> dict[str, float]:
    s = get_org_settings(db)
    return {
        "environmental": float(s.weight_env),
        "social": float(s.weight_social),
        "governance": float(s.weight_gov),
    }


# --- component calculators ---


def _goal_progress(goal: EnvironmentalGoal) -> float:
    if goal.status == GoalStatus.completed:
        return 100.0
    baseline = float(goal.baseline_value)
    target = float(goal.target_value)
    current = float(goal.current_value)
    if target == baseline:
        return 100.0 if current >= target else 0.0
    pct = (current - baseline) / (target - baseline) * 100.0
    return max(0.0, min(100.0, pct))


# --- the single-pass computation ---


def compute_all_departments(
    db: Session,
    start: dt.date,
    end: dt.date,
    weights: dict[str, float] | None = None,
) -> dict[int, DeptScore]:
    """Compute every scoreable department's ESG score for the period.

    A department is scoreable iff it has at least one active direct employee.
    """
    weights = weights or _weights(db)

    # 1) active employees + gender split per department (one query)
    gender_rows = db.execute(
        select(User.department_id, User.gender, func.count(User.id))
        .where(User.is_active.is_(True), User.department_id.is_not(None))
        .group_by(User.department_id, User.gender)
    ).all()
    emp_count: dict[int, int] = {}
    gender_split: dict[int, dict[Gender, int]] = {}
    for dept_id, gender, n in gender_rows:
        emp_count[dept_id] = emp_count.get(dept_id, 0) + n
        gender_split.setdefault(dept_id, {})[gender] = n

    scoreable = {d for d, n in emp_count.items() if n > 0}
    if not scoreable:
        return {}

    dept_names = {
        d.id: d.name
        for d in db.execute(select(Department)).scalars().all()
    }

    # 2) emissions per department in the period (one query)
    emis_rows = db.execute(
        select(CarbonTransaction.department_id, func.sum(CarbonTransaction.co2e_kg))
        .where(
            CarbonTransaction.activity_date >= start,
            CarbonTransaction.activity_date <= end,
        )
        .group_by(CarbonTransaction.department_id)
    ).all()
    emissions: dict[int, float] = {d: float(v or 0) for d, v in emis_rows}

    # emission performance: min-max of per-employee emissions across scoreable depts
    per_emp_emis = {d: emissions.get(d, 0.0) / emp_count[d] for d in scoreable}
    mn = min(per_emp_emis.values())
    mx = max(per_emp_emis.values())

    def emission_score(dept_id: int) -> float:
        if mx == mn:
            return 100.0
        return (mx - per_emp_emis[dept_id]) / (mx - mn) * 100.0

    # 3) active+completed goals per department
    goals = db.execute(
        select(EnvironmentalGoal).where(
            EnvironmentalGoal.status.in_([GoalStatus.active, GoalStatus.completed]),
            EnvironmentalGoal.owner_department_id.is_not(None),
        )
    ).scalars().all()
    goals_by_dept: dict[int, list[EnvironmentalGoal]] = {}
    for g in goals:
        goals_by_dept.setdefault(g.owner_department_id, []).append(g)

    # 4) distinct approved CSR participants per department (active employees)
    csr_rows = db.execute(
        select(User.department_id, func.count(func.distinct(CSRParticipation.user_id)))
        .join(User, CSRParticipation.user_id == User.id)
        .where(
            User.is_active.is_(True),
            CSRParticipation.status == ParticipationStatus.approved,
        )
        .group_by(User.department_id)
    ).all()
    csr_participants: dict[int, int] = {d: n for d, n in csr_rows if d is not None}

    # 5) training: active trainings (global) + completions per department
    active_trainings = db.execute(
        select(func.count(Training.id)).where(Training.status == TrainingStatus.active)
    ).scalar() or 0
    train_rows = db.execute(
        select(User.department_id, func.count(TrainingCompletion.id))
        .join(User, TrainingCompletion.user_id == User.id)
        .join(Training, TrainingCompletion.training_id == Training.id)
        .where(User.is_active.is_(True), Training.status == TrainingStatus.active)
        .group_by(User.department_id)
    ).all()
    train_completions: dict[int, int] = {d: n for d, n in train_rows if d is not None}

    # 6) policy: published policies + current-version acks per department
    published_policies = db.execute(
        select(func.count(ESGPolicy.id)).where(ESGPolicy.status == PolicyStatus.published)
    ).scalar() or 0
    ack_rows = db.execute(
        select(User.department_id, func.count(PolicyAcknowledgement.id))
        .join(ESGPolicy, PolicyAcknowledgement.policy_id == ESGPolicy.id)
        .join(User, PolicyAcknowledgement.user_id == User.id)
        .where(
            User.is_active.is_(True),
            ESGPolicy.status == PolicyStatus.published,
            PolicyAcknowledgement.policy_version == ESGPolicy.version,
        )
        .group_by(User.department_id)
    ).all()
    policy_acks: dict[int, int] = {d: n for d, n in ack_rows if d is not None}

    # 7) completed audit scores per department
    audit_rows = db.execute(
        select(Audit.department_id, Audit.score).where(
            Audit.status == AuditStatus.completed, Audit.score.is_not(None)
        )
    ).all()
    audit_scores: dict[int, list[float]] = {}
    for d, score in audit_rows:
        if d is not None:
            audit_scores.setdefault(d, []).append(float(score))

    # 8) compliance issues per department
    today = today_ist()
    issue_rows = db.execute(
        select(
            ComplianceIssue.department_id,
            ComplianceIssue.status,
            ComplianceIssue.is_overdue,
            ComplianceIssue.due_date,
        )
    ).all()
    issue_total: dict[int, int] = {}
    issue_closed: dict[int, int] = {}
    issue_overdue_open: dict[int, int] = {}
    for d, status, is_overdue, due in issue_rows:
        if d is None:
            continue
        issue_total[d] = issue_total.get(d, 0) + 1
        if status in (IssueStatus.resolved, IssueStatus.closed):
            issue_closed[d] = issue_closed.get(d, 0) + 1
        elif status in (IssueStatus.open, IssueStatus.in_progress) and (
            is_overdue or (due is not None and due < today)
        ):
            issue_overdue_open[d] = issue_overdue_open.get(d, 0) + 1

    # --- assemble per department ---
    result: dict[int, DeptScore] = {}
    for dept_id in scoreable:
        n_emp = emp_count[dept_id]
        components: list[Component] = []

        # Environmental -------------------------------------------------
        dept_goals = goals_by_dept.get(dept_id, [])
        if dept_goals:
            progresses = [_goal_progress(g) for g in dept_goals]
            goal_val = sum(progresses) / len(progresses)
            goal_inputs = {"goals": len(dept_goals), "avg_progress_pct": round(goal_val, 1)}
        else:
            goal_val = None
            goal_inputs = {"goals": 0}
        components.append(Component("goal_completion", "Goal completion", goal_val, goal_inputs))

        emis_val = emission_score(dept_id)
        components.append(
            Component(
                "emission_performance",
                "Emission performance",
                emis_val,
                {
                    "period_co2e_kg": round(emissions.get(dept_id, 0.0), 1),
                    "per_employee_kg": round(per_emp_emis[dept_id], 1),
                    "org_best_kg": round(mn, 1),
                    "org_worst_kg": round(mx, 1),
                },
            )
        )

        # Social --------------------------------------------------------
        participants = csr_participants.get(dept_id, 0)
        csr_val = participants / n_emp * 100.0
        components.append(
            Component(
                "csr_participation",
                "CSR participation",
                csr_val,
                {"participants": participants, "employees": n_emp},
            )
        )

        gsplit = gender_split.get(dept_id, {})
        male = gsplit.get(Gender.male, 0)
        female = gsplit.get(Gender.female, 0)
        male_share = male / n_emp
        female_share = female / n_emp
        diversity_val = 100.0 * (1 - abs(male_share - female_share))
        components.append(
            Component(
                "diversity_balance",
                "Diversity balance",
                diversity_val,
                {"male": male, "female": female, "employees": n_emp},
            )
        )

        if active_trainings > 0:
            required = active_trainings * n_emp
            done = train_completions.get(dept_id, 0)
            train_val = done / required * 100.0 if required else None
            train_inputs = {
                "completions": done,
                "active_trainings": active_trainings,
                "employees": n_emp,
            }
        else:
            train_val = None
            train_inputs = {"active_trainings": 0}
        components.append(
            Component("training_completion", "Training completion", train_val, train_inputs)
        )

        # Governance ----------------------------------------------------
        if published_policies > 0:
            required_acks = published_policies * n_emp
            done_acks = policy_acks.get(dept_id, 0)
            policy_val = done_acks / required_acks * 100.0 if required_acks else None
            policy_inputs = {
                "acknowledged": done_acks,
                "published_policies": published_policies,
                "employees": n_emp,
            }
        else:
            policy_val = None
            policy_inputs = {"published_policies": 0}
        components.append(
            Component("policy_ack", "Policy acknowledgement", policy_val, policy_inputs)
        )

        scores = audit_scores.get(dept_id, [])
        if scores:
            audit_val = sum(scores) / len(scores)
            audit_inputs = {"audits": len(scores), "avg_score": round(audit_val, 1)}
        else:
            audit_val = None
            audit_inputs = {"audits": 0}
        components.append(Component("audit_score", "Audit performance", audit_val, audit_inputs))

        total_issues = issue_total.get(dept_id, 0)
        closed = issue_closed.get(dept_id, 0)
        overdue_open = issue_overdue_open.get(dept_id, 0)
        base_health = 100.0 if total_issues == 0 else closed / total_issues * 100.0
        health_val = max(0.0, base_health - 5.0 * overdue_open)
        components.append(
            Component(
                "compliance_health",
                "Compliance health",
                health_val,
                {"resolved_closed": closed, "total_issues": total_issues, "overdue_open": overdue_open},
            )
        )

        # Pillars + total ----------------------------------------------
        by_key = {c.key: c.value for c in components}
        env = pillar_mean([by_key["goal_completion"], by_key["emission_performance"]])
        social = pillar_mean(
            [by_key["csr_participation"], by_key["diversity_balance"], by_key["training_completion"]]
        )
        gov = pillar_mean(
            [by_key["policy_ack"], by_key["audit_score"], by_key["compliance_health"]]
        )
        total = weighted_total(env, social, gov, weights)

        result[dept_id] = DeptScore(
            department_id=dept_id,
            department_name=dept_names.get(dept_id, f"Dept {dept_id}"),
            employee_count=n_emp,
            environmental=env,
            social=social,
            governance=gov,
            total=total,
            components=components,
        )

    return result


def compute_org_score(
    db: Session,
    start: dt.date,
    end: dt.date,
    weights: dict[str, float] | None = None,
    depts: dict[int, DeptScore] | None = None,
) -> OrgScore:
    """Employee-count-weighted mean of department totals (and pillars)."""
    depts = compute_all_departments(db, start, end, weights) if depts is None else depts
    dept_list = sorted(depts.values(), key=lambda d: d.total, reverse=True)
    if not dept_list:
        return OrgScore(None, None, None, 0.0, 0, [])

    def weighted(attr: str) -> float | None:
        num = 0.0
        den = 0
        for d in dept_list:
            v = getattr(d, attr)
            if v is not None:
                num += v * d.employee_count
                den += d.employee_count
        return num / den if den else None

    total_emp = sum(d.employee_count for d in dept_list)
    total = (
        sum(d.total * d.employee_count for d in dept_list) / total_emp
        if total_emp
        else 0.0
    )
    return OrgScore(
        environmental=weighted("environmental"),
        social=weighted("social"),
        governance=weighted("governance"),
        total=total,
        dept_count=len(dept_list),
        departments=dept_list,
    )


def compute_period(
    db: Session,
    period: str | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> tuple[OrgScore, dt.date, dt.date]:
    start, end = resolve_period(period, date_from, date_to)
    org = compute_org_score(db, start, end)
    return org, start, end


# --- snapshot persistence (used by the recalc endpoint, handlers, nightly job, seed) ---


def _upsert_dept_snapshot(
    db: Session, dept: DeptScore, snapshot_date: dt.date, period_type: str
) -> None:
    row = db.execute(
        select(DepartmentScoreSnapshot).where(
            DepartmentScoreSnapshot.department_id == dept.department_id,
            DepartmentScoreSnapshot.snapshot_date == snapshot_date,
            DepartmentScoreSnapshot.period_type == period_type,
        )
    ).scalar_one_or_none()
    components_json = {
        "environmental": _r(dept.environmental),
        "social": _r(dept.social),
        "governance": _r(dept.governance),
        "components": [c.as_dict() for c in dept.components],
    }
    if row:
        row.environmental_score = dept.environmental
        row.social_score = dept.social
        row.governance_score = dept.governance
        row.total_score = dept.total
        row.components_json = components_json
    else:
        db.add(
            DepartmentScoreSnapshot(
                department_id=dept.department_id,
                snapshot_date=snapshot_date,
                period_type=period_type,
                environmental_score=dept.environmental,
                social_score=dept.social,
                governance_score=dept.governance,
                total_score=dept.total,
                components_json=components_json,
            )
        )


def _upsert_org_snapshot(
    db: Session, org: OrgScore, snapshot_date: dt.date, period_type: str
) -> None:
    row = db.execute(
        select(OrgScoreSnapshot).where(
            OrgScoreSnapshot.snapshot_date == snapshot_date,
            OrgScoreSnapshot.period_type == period_type,
        )
    ).scalar_one_or_none()
    if row:
        row.environmental_score = org.environmental
        row.social_score = org.social
        row.governance_score = org.governance
        row.total_score = org.total
        row.dept_count = org.dept_count
    else:
        db.add(
            OrgScoreSnapshot(
                snapshot_date=snapshot_date,
                period_type=period_type,
                environmental_score=org.environmental,
                social_score=org.social,
                governance_score=org.governance,
                total_score=org.total,
                dept_count=org.dept_count,
            )
        )


def snapshot_scores(
    db: Session,
    period_type: str = "fy",
    snapshot_date: dt.date | None = None,
) -> OrgScore:
    """Compute the current FY scores and upsert dept + org snapshots for today.

    Flushes but does not commit (caller owns the transaction).
    """
    snapshot_date = snapshot_date or today_ist()
    start, end = resolve_period(period_type)
    org = compute_org_score(db, start, end)
    for dept in org.departments:
        _upsert_dept_snapshot(db, dept, snapshot_date, period_type)
    _upsert_org_snapshot(db, org, snapshot_date, period_type)
    db.flush()
    return org


def run_nightly_snapshot(db: Session) -> str:
    """Scheduler entry point (called via a deferred import from scheduler.py)."""
    org = snapshot_scores(db)
    return f"org ESG score {round(org.total, 1)} across {org.dept_count} departments"
