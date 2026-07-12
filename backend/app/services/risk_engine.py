import datetime as dt
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session

from app.models.core import Department, User, Notification
from app.models.enums import (
    ActiveStatus,
    AuditStatus,
    GoalStatus,
    IssueStatus,
    NotificationType,
    PolicyStatus,
    Role,
    TrainingStatus,
    ParticipationStatus,
)
from app.models.environment import CarbonTransaction
from app.models.gamification import XPTransaction
from app.models.governance import Audit, ComplianceIssue
from app.models.masterdata import (
    EnvironmentalGoal,
    ESGPolicy,
    PolicyAcknowledgement,
    Training,
    TrainingCompletion,
)
from app.models.social import CSRParticipation
from app.models.carbon_accounting import DepartmentCarbonBudget
from app.models.risk import DepartmentRiskSnapshot, RiskAlert
from app.services.notify import notify
from app.services.events import emit
from app.utils.time import today_ist, now_utc


def get_previous_risk_snapshot(
    db: Session, department_id: int, before_date: dt.date
) -> DepartmentRiskSnapshot | None:
    """Get the most recent risk snapshot for a department before a given date."""
    return db.execute(
        select(DepartmentRiskSnapshot)
        .where(
            DepartmentRiskSnapshot.department_id == department_id,
            DepartmentRiskSnapshot.snapshot_date < before_date,
        )
        .order_by(DepartmentRiskSnapshot.snapshot_date.desc(), DepartmentRiskSnapshot.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def calculate_environmental_points(db: Session, department_id: int, today: dt.date) -> float:
    """Calculate Environmental Risk Points (max 65)."""
    # 1. Carbon Emission Growth (max 25)
    # Current month emissions
    cur_start = today.replace(day=1)
    # End of current month
    if today.month == 12:
        cur_end = dt.date(today.year + 1, 1, 1) - dt.timedelta(days=1)
    else:
        cur_end = dt.date(today.year, today.month + 1, 1) - dt.timedelta(days=1)

    # Previous month
    if today.month == 1:
        prev_start = dt.date(today.year - 1, 12, 1)
        prev_end = dt.date(today.year, 1, 1) - dt.timedelta(days=1)
    else:
        prev_start = dt.date(today.year, today.month - 1, 1)
        prev_end = cur_start - dt.timedelta(days=1)

    cur_emissions = float(db.execute(
        select(func.sum(CarbonTransaction.co2e_kg)).where(
            CarbonTransaction.department_id == department_id,
            CarbonTransaction.activity_date >= cur_start,
            CarbonTransaction.activity_date <= cur_end,
        )
    ).scalar() or 0.0)

    prev_emissions = float(db.execute(
        select(func.sum(CarbonTransaction.co2e_kg)).where(
            CarbonTransaction.department_id == department_id,
            CarbonTransaction.activity_date >= prev_start,
            CarbonTransaction.activity_date <= prev_end,
        )
    ).scalar() or 0.0)

    growth_points = 0.0
    if prev_emissions > 0:
        growth_pct = ((cur_emissions - prev_emissions) / prev_emissions) * 100.0
        if growth_pct > 15.0:
            growth_points = 25.0
        elif growth_pct >= 5.0:
            growth_points = 15.0
        elif growth_pct > 0.0:
            growth_points = 5.0
    elif cur_emissions > 0:
        # Prev emissions is 0, cur is positive -> 100% growth
        growth_points = 25.0

    # 2. Environmental Goal Performance (max 20)
    goals = db.execute(
        select(EnvironmentalGoal).where(EnvironmentalGoal.owner_department_id == department_id)
    ).scalars().all()

    goal_points = 0.0
    if goals:
        completed = sum(1 for g in goals if g.status == GoalStatus.completed)
        missed = sum(
            1 for g in goals 
            if g.status == GoalStatus.missed or (g.status == GoalStatus.active and g.deadline < today)
        )
        total = completed + missed
        if total > 0:
            comp_pct = (completed / total) * 100.0
            if comp_pct < 70.0:
                goal_points = 20.0
            elif comp_pct <= 90.0:
                goal_points = 10.0

    # 3. Carbon Budget Overrun (max 20)
    # Find active budget for current fiscal year/period
    # For seeding/demo simplicity we lookup budget starting before today and ending after today
    budget = db.execute(
        select(DepartmentCarbonBudget)
        .where(
            DepartmentCarbonBudget.department_id == department_id,
            DepartmentCarbonBudget.start_date <= today,
            DepartmentCarbonBudget.end_date >= today,
        )
        .limit(1)
    ).scalar_one_or_none()

    budget_points = 0.0
    if budget:
        # Sum actual emissions in budget range
        act_emissions = db.execute(
            select(func.sum(CarbonTransaction.co2e_kg)).where(
                CarbonTransaction.department_id == department_id,
                CarbonTransaction.activity_date >= budget.start_date,
                CarbonTransaction.activity_date <= budget.end_date,
            )
        ).scalar() or 0.0
        act_tons = float(act_emissions) / 1000.0
        
        if act_tons > budget.budgeted_co2e_tons:
            overrun_pct = ((act_tons - budget.budgeted_co2e_tons) / budget.budgeted_co2e_tons) * 100.0
            if overrun_pct > 10.0:
                budget_points = 20.0
            else:
                budget_points = 10.0

    return growth_points + goal_points + budget_points


def calculate_social_points(db: Session, department_id: int, today: dt.date) -> float:
    """Calculate Social Risk Points (max 55)."""
    # Total department employees
    emp_count = db.execute(
        select(func.count(User.id)).where(User.department_id == department_id, User.is_active.is_(True))
    ).scalar() or 0

    if emp_count == 0:
        return 0.0

    # 1. CSR Participation Rate (max 20)
    # Distinct employees with approved CSR participations
    csr_parts = db.execute(
        select(func.count(func.distinct(CSRParticipation.user_id)))
        .join(User, CSRParticipation.user_id == User.id)
        .where(
            User.department_id == department_id,
            CSRParticipation.status == ParticipationStatus.approved
        )
    ).scalar() or 0

    csr_points = 20.0
    csr_pct = (csr_parts / emp_count) * 100.0
    if csr_pct > 70.0:
        csr_points = 0.0
    elif csr_pct >= 40.0:
        csr_points = 10.0

    # 2. Training Completion (max 20)
    active_trainings_count = db.execute(
        select(func.count(Training.id)).where(Training.status == TrainingStatus.active)
    ).scalar() or 0

    training_points = 0.0
    if active_trainings_count > 0:
        required_completions = active_trainings_count * emp_count
        actual_completions = db.execute(
            select(func.count(TrainingCompletion.id))
            .join(User, TrainingCompletion.user_id == User.id)
            .join(Training, TrainingCompletion.training_id == Training.id)
            .where(
                User.department_id == department_id,
                User.is_active.is_(True),
                Training.status == TrainingStatus.active
            )
        ).scalar() or 0

        train_pct = (actual_completions / required_completions) * 100.0
        if train_pct < 80.0:
            training_points = 20.0
        elif train_pct <= 95.0:
            training_points = 10.0

    # 3. Employee Engagement (max 15)
    # Inactive employees: 0 XP earned in the last 30 days
    start_date = today - dt.timedelta(days=30)
    active_users = db.execute(
        select(User.id).where(User.department_id == department_id, User.is_active.is_(True))
    ).scalars().all()

    active_xp_users = set(
        db.execute(
            select(XPTransaction.user_id)
            .join(User, XPTransaction.user_id == User.id)
            .where(
                User.department_id == department_id,
                XPTransaction.created_at >= start_date,
                XPTransaction.amount > 0
            )
        ).scalars().all()
    )

    inactive_count = sum(1 for uid in active_users if uid not in active_xp_users)
    inactive_pct = (inactive_count / emp_count) * 100.0

    engagement_points = 15.0 if inactive_pct > 50.0 else 0.0

    return csr_points + training_points + engagement_points


def calculate_governance_points(db: Session, department_id: int, today: dt.date) -> float:
    """Calculate Governance Risk Points (max 65)."""
    # Total department employees
    emp_count = db.execute(
        select(func.count(User.id)).where(User.department_id == department_id, User.is_active.is_(True))
    ).scalar() or 0

    if emp_count == 0:
        return 0.0

    # 1. Policy Acknowledgements (max 20)
    published_policies_count = db.execute(
        select(func.count(ESGPolicy.id)).where(ESGPolicy.status == PolicyStatus.published)
    ).scalar() or 0

    policy_points = 0.0
    if published_policies_count > 0:
        required_acks = published_policies_count * emp_count
        
        # Acks for current versions of published policies by active employees in the department
        completed_acks = db.execute(
            select(func.count(PolicyAcknowledgement.id))
            .join(ESGPolicy, PolicyAcknowledgement.policy_id == ESGPolicy.id)
            .join(User, PolicyAcknowledgement.user_id == User.id)
            .where(
                User.department_id == department_id,
                User.is_active.is_(True),
                ESGPolicy.status == PolicyStatus.published,
                PolicyAcknowledgement.policy_version == ESGPolicy.version
            )
        ).scalar() or 0

        ack_pct = (completed_acks / required_acks) * 100.0
        if ack_pct < 80.0:
            policy_points = 20.0
        elif ack_pct <= 95.0:
            policy_points = 10.0

    # 2. Open Compliance Issues (max 25)
    open_count = db.execute(
        select(func.count(ComplianceIssue.id)).where(
            ComplianceIssue.department_id == department_id,
            ComplianceIssue.status.in_([IssueStatus.open, IssueStatus.in_progress])
        )
    ).scalar() or 0

    overdue_count = db.execute(
        select(func.count(ComplianceIssue.id)).where(
            ComplianceIssue.department_id == department_id,
            ComplianceIssue.status.in_([IssueStatus.open, IssueStatus.in_progress]),
            or_(ComplianceIssue.is_overdue.is_(True), ComplianceIssue.due_date < today)
        )
    ).scalar() or 0

    issue_points = min(25.0, (2.0 * open_count) + (5.0 * overdue_count))

    # 3. Audit Performance (max 20)
    completed_audits = db.execute(
        select(Audit.score).where(
            Audit.department_id == department_id,
            Audit.status == AuditStatus.completed
        )
    ).scalars().all()

    audit_points = 0.0
    if completed_audits:
        avg_score = sum(completed_audits) / len(completed_audits)
        if avg_score < 75.0:
            audit_points = 20.0
        elif avg_score <= 90.0:
            audit_points = 10.0

    return policy_points + issue_points + audit_points


def recalculate_department_risk(
    db: Session, department_id: int, snapshot_date: dt.date | None = None,
    *, actor_id: int | None = None,
) -> DepartmentRiskSnapshot:
    """Evaluate and store risk snapshot for a department."""
    if snapshot_date is None:
        snapshot_date = today_ist()

    # Calculate raw points
    env_pts = calculate_environmental_points(db, department_id, snapshot_date)
    soc_pts = calculate_social_points(db, department_id, snapshot_date)
    gov_pts = calculate_governance_points(db, department_id, snapshot_date)

    # Normalize to 0-100 scale for each pillar
    # Env max is 65, Soc max is 55, Gov max is 65
    env_norm = (env_pts / 65.0) * 100.0
    soc_norm = (soc_pts / 55.0) * 100.0
    gov_norm = (gov_pts / 65.0) * 100.0

    overall = (0.4 * env_norm) + (0.3 * soc_norm) + (0.3 * gov_norm)

    # Check if snapshot already exists for department + date
    snapshot = db.execute(
        select(DepartmentRiskSnapshot).where(
            DepartmentRiskSnapshot.department_id == department_id,
            DepartmentRiskSnapshot.snapshot_date == snapshot_date
        )
    ).scalar_one_or_none()

    if snapshot:
        snapshot.environmental_risk = env_norm
        snapshot.social_risk = soc_norm
        snapshot.governance_risk = gov_norm
        snapshot.overall_risk = overall
    else:
        snapshot = DepartmentRiskSnapshot(
            department_id=department_id,
            snapshot_date=snapshot_date,
            environmental_risk=env_norm,
            social_risk=soc_norm,
            governance_risk=gov_norm,
            overall_risk=overall,
        )
        db.add(snapshot)

    db.flush()

    # Trigger alerts checks
    prev = get_previous_risk_snapshot(db, department_id, snapshot_date)
    check_and_trigger_alerts(db, department_id, prev, snapshot)

    emit(
        db,
        "risk.snapshot.updated",
        department_id=department_id,
        entity_type="department_risk_snapshot",
        entity_id=snapshot.id,
        actor_id=actor_id,
        payload={"risk_score": float(snapshot.overall_risk)},
    )

    return snapshot


def recalculate_all_departments(db: Session, *, actor_id: int | None = None) -> int:
    department_ids = list(db.scalars(select(Department.id)).all())
    for department_id in department_ids:
        recalculate_department_risk(db, department_id, actor_id=actor_id)
    return len(department_ids)


def check_and_trigger_alerts(
    db: Session,
    department_id: int,
    prev: DepartmentRiskSnapshot | None,
    current: DepartmentRiskSnapshot,
) -> None:
    """Send system notifications if risk flags are triggered."""
    dept = db.get(Department, department_id)
    if not dept:
        return

    # Helper to send alert
    def send_alert(alert_type: str, title: str, body: str):
        # Prevent duplicate alerts of same type in same day
        start_of_day = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
        dup = db.execute(
            select(RiskAlert).where(
                RiskAlert.department_id == department_id,
                RiskAlert.alert_type == alert_type,
                RiskAlert.timestamp >= start_of_day
            )
        ).scalar_one_or_none()
        if dup:
            return

        alert = RiskAlert(
            department_id=department_id,
            risk_score=current.overall_risk,
            alert_type=alert_type,
            message=body,
        )
        db.add(alert)
        db.flush()
        emit(
            db,
            "risk.alert.raised",
            department_id=department_id,
            entity_type="risk_alert",
            entity_id=alert.id,
            payload={"alert_type": alert_type, "risk_score": float(current.overall_risk)},
        )

        # Retrieve ESG Managers + Department Head
        recipients = db.execute(
            select(User).where(
                or_(
                    User.role == Role.esg_manager,
                    User.id == dept.head_user_id
                ),
                User.is_active.is_(True)
            )
        ).scalars().all()

        for u in recipients:
            notify(
                db,
                u,
                NotificationType.risk_alert,
                title,
                body,
                entity_type="Department",
                entity_id=department_id,
            )

    # 1. Exceeds 70
    if current.overall_risk > 70.0 and (not prev or prev.overall_risk <= 70.0):
        send_alert(
            "threshold_exceeded",
            f"High ESG Risk Alert: {dept.name}",
            f"ESG risk score for {dept.name} has exceeded 70 (Current: {current.overall_risk:.1f}/100).",
        )

    # 2. Critical Status
    if current.overall_risk >= 81.0 and (not prev or prev.overall_risk < 81.0):
        send_alert(
            "critical_status",
            f"Critical ESG Risk: {dept.name}",
            f"{dept.name} department has entered Critical Risk status with a score of {current.overall_risk:.1f}/100.",
        )

    # 3. Monthly Increase by > 15 points
    if prev and (current.overall_risk - prev.overall_risk) > 15.0:
        send_alert(
            "monthly_increase",
            f"Rapid Risk Surge: {dept.name}",
            f"Risk score for {dept.name} increased by {current.overall_risk - prev.overall_risk:.1f} points this month (from {prev.overall_risk:.1f} to {current.overall_risk:.1f}).",
        )


def generate_risk_insights(db: Session, department_id: int) -> dict:
    """Generate risk contributors, recommendations, and AI insights text."""
    dept = db.get(Department, department_id)
    if not dept:
        return {}

    today = today_ist()
    env_pts = calculate_environmental_points(db, department_id, today)
    soc_pts = calculate_social_points(db, department_id, today)
    gov_pts = calculate_governance_points(db, department_id, today)

    env_norm = (env_pts / 65.0) * 100.0
    soc_norm = (soc_pts / 55.0) * 100.0
    gov_norm = (gov_pts / 65.0) * 100.0
    overall = (0.4 * env_norm) + (0.3 * soc_norm) + (0.3 * gov_norm)

    contributors = []
    recommendations = []

    # Get data specifics for insights
    cur_start = today.replace(day=1)
    if today.month == 12:
        cur_end = dt.date(today.year + 1, 1, 1) - dt.timedelta(days=1)
    else:
        cur_end = dt.date(today.year, today.month + 1, 1) - dt.timedelta(days=1)
    if today.month == 1:
        prev_start = dt.date(today.year - 1, 12, 1)
        prev_end = dt.date(today.year, 1, 1) - dt.timedelta(days=1)
    else:
        prev_start = dt.date(today.year, today.month - 1, 1)
        prev_end = cur_start - dt.timedelta(days=1)

    cur_emissions = db.execute(
        select(func.sum(CarbonTransaction.co2e_kg)).where(
            CarbonTransaction.department_id == department_id,
            CarbonTransaction.activity_date >= cur_start,
            CarbonTransaction.activity_date <= cur_end,
        )
    ).scalar() or 0.0
    prev_emissions = db.execute(
        select(func.sum(CarbonTransaction.co2e_kg)).where(
            CarbonTransaction.department_id == department_id,
            CarbonTransaction.activity_date >= prev_start,
            CarbonTransaction.activity_date <= prev_end,
        )
    ).scalar() or 0.0

    if prev_emissions > 0 and cur_emissions > prev_emissions:
        growth = ((cur_emissions - prev_emissions) / prev_emissions) * 100.0
        contributors.append(f"Carbon emissions increased by {growth:.1f}% compared to last period.")
        recommendations.append("Reduce diesel fleet and electricity usage.")

    # Budget
    budget = db.execute(
        select(DepartmentCarbonBudget)
        .where(
            DepartmentCarbonBudget.department_id == department_id,
            DepartmentCarbonBudget.start_date <= today,
            DepartmentCarbonBudget.end_date >= today,
        )
    ).scalar_one_or_none()
    if budget:
        act_emissions = db.execute(
            select(func.sum(CarbonTransaction.co2e_kg)).where(
                CarbonTransaction.department_id == department_id,
                CarbonTransaction.activity_date >= budget.start_date,
                CarbonTransaction.activity_date <= budget.end_date,
            )
        ).scalar() or 0.0
        act_tons = float(act_emissions) / 1000.0
        if act_tons > budget.budgeted_co2e_tons:
            overrun_pct = ((act_tons - budget.budgeted_co2e_tons) / budget.budgeted_co2e_tons) * 100.0
            contributors.append(f"Emissions exceed department carbon budget by {overrun_pct:.1f}%.")
            recommendations.append("Implement carbon reduction measures to align with department budget.")

    # Issues
    open_count = db.execute(
        select(func.count(ComplianceIssue.id)).where(
            ComplianceIssue.department_id == department_id,
            ComplianceIssue.status.in_([IssueStatus.open, IssueStatus.in_progress])
        )
    ).scalar() or 0
    overdue_count = db.execute(
        select(func.count(ComplianceIssue.id)).where(
            ComplianceIssue.department_id == department_id,
            ComplianceIssue.status.in_([IssueStatus.open, IssueStatus.in_progress]),
            or_(ComplianceIssue.is_overdue.is_(True), ComplianceIssue.due_date < today)
        )
    ).scalar() or 0

    if open_count > 0:
        contributors.append(f"Department has {open_count} unresolved compliance issue(s) ({overdue_count} overdue).")
        recommendations.append("Resolve overdue compliance tickets and close open issues.")

    # Goals
    goals = db.execute(
        select(EnvironmentalGoal).where(EnvironmentalGoal.owner_department_id == department_id)
    ).scalars().all()
    if goals:
        completed = sum(1 for g in goals if g.status == GoalStatus.completed)
        total = len(goals)
        comp_pct = (completed / total) * 100.0 if total > 0 else 100.0
        if comp_pct < 90.0:
            contributors.append(f"Overdue or missed sustainability goals ({comp_pct:.1f}% completed).")
            recommendations.append("Launch department sustainability challenge or re-assign goals.")

    # Training
    emp_count = db.execute(
        select(func.count(User.id)).where(User.department_id == department_id, User.is_active.is_(True))
    ).scalar() or 0
    if emp_count > 0:
        active_trainings_count = db.execute(
            select(func.count(Training.id)).where(Training.status == TrainingStatus.active)
        ).scalar() or 0
        if active_trainings_count > 0:
            required_completions = active_trainings_count * emp_count
            actual_completions = db.execute(
                select(func.count(TrainingCompletion.id))
                .join(User, TrainingCompletion.user_id == User.id)
                .join(Training, TrainingCompletion.training_id == Training.id)
                .where(
                    User.department_id == department_id,
                    User.is_active.is_(True),
                    Training.status == TrainingStatus.active
                )
            ).scalar() or 0
            train_pct = (actual_completions / required_completions) * 100.0
            if train_pct < 95.0:
                contributors.append(f"Mandatory training completion is low ({train_pct:.1f}%).")
                recommendations.append("Complete pending training assignments and send reminders.")

    # Policies
    published_policies_count = db.execute(
        select(func.count(ESGPolicy.id)).where(ESGPolicy.status == PolicyStatus.published)
    ).scalar() or 0
    if published_policies_count > 0 and emp_count > 0:
        required_acks = published_policies_count * emp_count
        completed_acks = db.execute(
            select(func.count(PolicyAcknowledgement.id))
            .join(ESGPolicy, PolicyAcknowledgement.policy_id == ESGPolicy.id)
            .join(User, PolicyAcknowledgement.user_id == User.id)
            .where(
                User.department_id == department_id,
                User.is_active.is_(True),
                ESGPolicy.status == PolicyStatus.published,
                PolicyAcknowledgement.policy_version == ESGPolicy.version
            )
        ).scalar() or 0
        ack_pct = (completed_acks / required_acks) * 100.0
        if ack_pct < 95.0:
            contributors.append(f"Policy acknowledgement rate is low ({ack_pct:.1f}%).")
            recommendations.append("Send reminders for pending policy acknowledgements.")

    # Audit
    completed_audits = db.execute(
        select(Audit.score).where(
            Audit.department_id == department_id,
            Audit.status == AuditStatus.completed
        )
    ).scalars().all()
    if completed_audits:
        avg_score = sum(completed_audits) / len(completed_audits)
        if avg_score < 90.0:
            contributors.append(f"Recent average audit score is low ({avg_score:.1f}/100).")
            recommendations.append("Review audit findings and implement corrective actions.")

    # Default contributors if empty
    if not contributors:
        contributors.append("No active risk factors identified.")
        recommendations.append("Maintain current sustainability and governance compliance levels.")

    # AI Insight Text
    prev_snapshot = get_previous_risk_snapshot(db, department_id, today)
    prev_val = prev_snapshot.overall_risk if prev_snapshot else 60.0 # fallback default for demo

    reasons_str = " and ".join(contributors[:2]) if contributors else "normal operations"
    insight_text = (
        f"{dept.name} department risk is evaluated at {overall:.1f}/100. "
        f"The main drivers are: {reasons_str}."
    )
    if prev_val and overall > prev_val:
        insight_text = (
            f"{dept.name} risk increased from {prev_val:.1f} to {overall:.1f} this month "
            f"due to: {reasons_str}."
        )

    return {
        "overall_risk": round(overall, 1),
        "environmental_risk": round(env_norm, 1),
        "social_risk": round(soc_norm, 1),
        "governance_risk": round(gov_norm, 1),
        "contributors": contributors,
        "recommendations": recommendations,
        "ai_insight": insight_text,
    }
