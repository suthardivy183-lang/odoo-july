import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin, require_esg, require_head
from app.db.session import get_db
from app.models.core import Department, User
from app.models.enums import ActiveStatus, AuditAction, IssueStatus, NotificationType, Role, Severity
from app.models.governance import ComplianceIssue
from app.models.risk import DepartmentRiskSnapshot, RiskAlert
from app.schemas.common import Msg, Page
from app.schemas.compliance import (
    ComplianceIssueCreate,
    ComplianceIssueOut,
    ComplianceIssueUpdate,
)
from app.schemas.risk import DepartmentRiskOut, DrillDownOut, RiskAlertOut
from app.services.audit import log_action, snapshot
from app.services.compliance_rules import refresh_overdue_flag
from app.services.notify import notify
from app.services.org import responsible_head
from app.services.risk_engine import (
    generate_risk_insights,
    recalculate_department_risk,
    get_previous_risk_snapshot,
)
from app.utils.time import now_utc, today_ist

router = APIRouter(tags=["Compliance"])


# --- COMPLIANCE ISSUES ENDPOINTS ---

@router.post("/compliance/issues", response_model=ComplianceIssueOut)
def create_compliance_issue(
    payload: ComplianceIssueCreate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    dept = db.get(Department, payload.department_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    if dept.status != ActiveStatus.active:
        raise HTTPException(status_code=400, detail="Cannot assign issue to an inactive department")

    owner = db.get(User, payload.owner_user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Owner user not found")

    issue = ComplianceIssue(
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        owner_user_id=payload.owner_user_id,
        due_date=payload.due_date,
        status=IssueStatus.open,
        department_id=payload.department_id,
        created_by=current.id,
    )
    db.add(issue)
    db.flush()

    refresh_overdue_flag(issue)
    db.flush()

    # Recalculate Risk Heatmap for this department instantly!
    recalculate_department_risk(db, issue.department_id)
    db.flush()

    # Send Notification: compliance_new
    recipients = [owner]
    head = responsible_head(db, issue.department_id)
    if head:
        recipients.append(head)
    esg_managers = db.execute(
        select(User).where(User.role == Role.esg_manager, User.is_active.is_(True))
    ).scalars().all()
    recipients.extend(esg_managers)

    # De-duplicate recipients
    recipient_ids = set()
    unique_recipients = []
    for r in recipients:
        if r.id not in recipient_ids:
            recipient_ids.add(r.id)
            unique_recipients.append(r)

    notify(
        db,
        unique_recipients,
        NotificationType.compliance_new,
        f"New compliance issue raised: {issue.title}",
        f"Severity {issue.severity.value.upper()} issue raised for {dept.name} department.",
        entity_type="compliance_issue",
        entity_id=issue.id,
    )

    log_action(
        db,
        current.id,
        AuditAction.create,
        "compliance_issue",
        issue.id,
        issue.title,
        after=snapshot(issue, ["title", "severity", "status"]),
    )

    db.commit()
    db.refresh(issue)

    out = ComplianceIssueOut.model_validate(issue)
    out.owner_name = owner.full_name
    out.department_name = dept.name
    return out


@router.get("/compliance/issues", response_model=Page[ComplianceIssueOut])
def list_compliance_issues(
    page: int = 1,
    size: int = Query(20, le=100),
    department_id: int | None = None,
    status: IssueStatus | None = None,
    owner_user_id: int | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * size
    query = select(ComplianceIssue).order_by(ComplianceIssue.id.desc())

    if department_id is not None:
        query = query.where(ComplianceIssue.department_id == department_id)
    if status is not None:
        query = query.where(ComplianceIssue.status == status)
    if owner_user_id is not None:
        query = query.where(ComplianceIssue.owner_user_id == owner_user_id)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = db.execute(query.offset(offset).limit(size)).scalars().all()

    dept_names = {d.id: d.name for d in db.execute(select(Department)).scalars().all()}
    user_names = {u.id: u.full_name for u in db.execute(select(User)).scalars().all()}

    out_items = []
    for issue in items:
        out = ComplianceIssueOut.model_validate(issue)
        out.owner_name = user_names.get(issue.owner_user_id)
        out.department_name = dept_names.get(issue.department_id)
        out_items.append(out)

    return Page[ComplianceIssueOut](items=out_items, total=total)


@router.patch("/compliance/issues/{issue_id}", response_model=ComplianceIssueOut)
def update_compliance_issue(
    issue_id: int,
    payload: ComplianceIssueUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    issue = db.get(ComplianceIssue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Compliance issue not found")

    # Authorize update: ESG/Admin always, or Owner/Head of department
    is_authorized = (
        current.role in (Role.admin, Role.esg_manager)
        or issue.owner_user_id == current.id
        or (current.role == Role.dept_head and current.department_id == issue.department_id)
    )
    if not is_authorized:
        raise HTTPException(status_code=403, detail="You do not have permission to edit this issue")

    before = snapshot(issue, ["title", "description", "severity", "owner_user_id", "due_date", "status", "department_id"])

    # Handle status transitions:
    # open->in_progress->resolved->closed
    # in_progress->open
    # resolved->closed
    # resolved->in_progress (reopen)
    if payload.status is not None and payload.status != issue.status:
        valid_transitions = {
            IssueStatus.open: [IssueStatus.in_progress],
            IssueStatus.in_progress: [IssueStatus.open, IssueStatus.resolved],
            IssueStatus.resolved: [IssueStatus.in_progress, IssueStatus.closed],
            IssueStatus.closed: []  # Closed is terminal unless reopened by ESG/Admin
        }
        # Admins can bypass transition rules
        if current.role not in (Role.admin, Role.esg_manager) and payload.status not in valid_transitions.get(issue.status, []):
            raise HTTPException(status_code=400, detail=f"Invalid status transition from {issue.status} to {payload.status}")

        issue.status = payload.status
        if payload.status == IssueStatus.resolved:
            issue.resolved_at = now_utc()
        elif payload.status in (IssueStatus.open, IssueStatus.in_progress):
            issue.resolved_at = None

    if payload.title is not None:
        issue.title = payload.title
    if payload.description is not None:
        issue.description = payload.description
    if payload.severity is not None:
        issue.severity = payload.severity
    if payload.owner_user_id is not None:
        owner = db.get(User, payload.owner_user_id)
        if owner is None:
            raise HTTPException(status_code=404, detail="Owner user not found")
        issue.owner_user_id = payload.owner_user_id
    if payload.due_date is not None:
        issue.due_date = payload.due_date
    if payload.department_id is not None:
        dept = db.get(Department, payload.department_id)
        if dept is None:
            raise HTTPException(status_code=404, detail="Department not found")
        issue.department_id = payload.department_id

    db.flush()

    refresh_overdue_flag(issue)
    db.flush()

    # Recalculate Risk Heatmap for this department instantly!
    recalculate_department_risk(db, issue.department_id)
    db.flush()

    log_action(
        db,
        current.id,
        AuditAction.update,
        "compliance_issue",
        issue.id,
        issue.title,
        before=before,
        after=snapshot(issue, ["title", "description", "severity", "owner_user_id", "due_date", "status", "department_id"]),
    )

    db.commit()
    db.refresh(issue)

    out = ComplianceIssueOut.model_validate(issue)
    out.owner_name = issue.owner.full_name if issue.owner else None
    out.department_name = issue.department.name if issue.department else None
    return out


# --- RISK HEATMAP ENDPOINTS ---

@router.get("/risk-heatmap", response_model=list[DepartmentRiskOut])
def get_risk_heatmap(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Recalculate risk for all departments to make sure it's up to date
    depts = db.execute(select(Department).where(Department.status == ActiveStatus.active)).scalars().all()
    today = today_ist()
    for d in depts:
        recalculate_department_risk(db, d.id, today)
    db.commit()

    # Get latest snapshots
    query = select(DepartmentRiskSnapshot).where(DepartmentRiskSnapshot.snapshot_date == today)
    snapshots = db.execute(query).scalars().all()

    out_items = []
    for s in snapshots:
        out = DepartmentRiskOut.model_validate(s)
        out.department_name = s.department.name if s.department else None
        out_items.append(out)

    return out_items


@router.get("/risk-heatmap/drilldown/{department_id}", response_model=DrillDownOut)
def get_risk_drilldown(
    department_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dept = db.get(Department, department_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")

    insights = generate_risk_insights(db, department_id)
    return DrillDownOut(
        overall_risk=insights["overall_risk"],
        environmental_risk=insights["environmental_risk"],
        social_risk=insights["social_risk"],
        governance_risk=insights["governance_risk"],
        contributors=insights["contributors"],
        recommendations=insights["recommendations"],
        ai_insight=insights["ai_insight"],
    )


@router.get("/risk-heatmap/alerts", response_model=Page[RiskAlertOut])
def get_risk_alerts(
    page: int = 1,
    size: int = Query(20, le=100),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * size
    query = select(RiskAlert).order_by(RiskAlert.timestamp.desc())

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = db.execute(query.offset(offset).limit(size)).scalars().all()

    out_items = []
    for alert in items:
        out = RiskAlertOut.model_validate(alert)
        out.department_name = alert.department.name if alert.department else None
        out_items.append(out)

    return Page[RiskAlertOut](items=out_items, total=total)


@router.get("/risk-heatmap/dashboard")
def get_risk_dashboard(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = today_ist()
    # 1. Highest Risk Department
    highest = db.execute(
        select(DepartmentRiskSnapshot)
        .where(DepartmentRiskSnapshot.snapshot_date == today)
        .order_by(DepartmentRiskSnapshot.overall_risk.desc())
        .limit(1)
    ).scalar_one_or_none()

    highest_dept = None
    if highest:
        highest_dept = {
            "name": highest.department.name if highest.department else None,
            "score": float(highest.overall_risk),
        }

    # 2. Critical Departments Count (overall_risk >= 81)
    critical_count = db.execute(
        select(func.count(DepartmentRiskSnapshot.id)).where(
            DepartmentRiskSnapshot.snapshot_date == today,
            DepartmentRiskSnapshot.overall_risk >= 81.0,
        )
    ).scalar() or 0

    # 3. Top Risk Drivers
    # Compile a count of common risk drivers across all departments
    all_depts = db.execute(select(Department).where(Department.status == ActiveStatus.active)).scalars().all()
    driver_counts = {}
    for d in all_depts:
        ins = generate_risk_insights(db, d.id)
        for c in ins.get("contributors", []):
            # clean string a bit to group
            clean_c = c.split(" (")[0].split(" by ")[0]
            driver_counts[clean_c] = driver_counts.get(clean_c, 0) + 1

    sorted_drivers = sorted(driver_counts.items(), key=lambda x: x[1], reverse=True)
    top_drivers = [{"driver": k, "count": v} for k, v in sorted_drivers[:4]]

    # 4. Trend of Risk Score over Time (average overall risk over past 6 months)
    months = []
    year, month = today.year, today.month
    for _ in range(6):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    months.reverse()

    trend = []
    for y, m in months:
        avg_score = db.execute(
            select(func.avg(DepartmentRiskSnapshot.overall_risk)).where(
                func.extract('year', DepartmentRiskSnapshot.snapshot_date) == y,
                func.extract('month', DepartmentRiskSnapshot.snapshot_date) == m,
            )
        ).scalar()
        
        # SQLite backup logic for testing
        if avg_score is None:
            # Try plain date comparison for SQLite
            start_date = dt.date(y, m, 1)
            if m == 12:
                end_date = dt.date(y + 1, 1, 1) - dt.timedelta(days=1)
            else:
                end_date = dt.date(y, m + 1, 1) - dt.timedelta(days=1)
            avg_score = db.execute(
                select(func.avg(DepartmentRiskSnapshot.overall_risk)).where(
                    DepartmentRiskSnapshot.snapshot_date >= start_date,
                    DepartmentRiskSnapshot.snapshot_date <= end_date,
                )
            ).scalar()

        trend.append({
            "month": f"{y:04d}-{m:02d}",
            "average_risk": round(float(avg_score), 1) if avg_score is not None else 0.0
        })

    # 5. Upcoming Compliance Deadlines (due in next 14 days)
    upcoming_limit = today + dt.timedelta(days=14)
    deadlines = db.execute(
        select(ComplianceIssue)
        .where(
            ComplianceIssue.status.in_([IssueStatus.open, IssueStatus.in_progress]),
            ComplianceIssue.due_date >= today,
            ComplianceIssue.due_date <= upcoming_limit
        )
        .order_by(ComplianceIssue.due_date.asc())
        .limit(5)
    ).scalars().all()

    upcoming_deadlines = [
        {
            "id": issue.id,
            "title": issue.title,
            "department_name": issue.department.name if issue.department else None,
            "due_date": issue.due_date.isoformat(),
            "severity": issue.severity.value,
        }
        for issue in deadlines
    ]

    # 6. Departments with Increasing Risk (today overall_risk > prev overall_risk)
    increasing_depts = []
    for d in all_depts:
        cur_snap = db.execute(
            select(DepartmentRiskSnapshot).where(
                DepartmentRiskSnapshot.department_id == d.id,
                DepartmentRiskSnapshot.snapshot_date == today
            )
        ).scalar_one_or_none()
        
        prev_snap = get_previous_risk_snapshot(db, d.id, today)
        if cur_snap and prev_snap and cur_snap.overall_risk > prev_snap.overall_risk:
            increasing_depts.append({
                "name": d.name,
                "previous_score": float(prev_snap.overall_risk),
                "current_score": float(cur_snap.overall_risk),
                "increase": float(cur_snap.overall_risk - prev_snap.overall_risk)
            })

    return {
        "highest_risk_department": highest_dept,
        "critical_departments_count": critical_count,
        "top_risk_drivers": top_drivers,
        "risk_trend": trend,
        "upcoming_compliance_deadlines": upcoming_deadlines,
        "departments_with_increasing_risk": increasing_depts,
    }
