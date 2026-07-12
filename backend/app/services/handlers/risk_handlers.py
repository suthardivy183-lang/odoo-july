import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.carbon_accounting import DepartmentCarbonBudget
from app.models.core import Department, User
from app.models.enums import NotificationType, Role
from app.models.events import DomainEvent
from app.models.risk import RiskAlert
from app.services.carbon_accounting import get_department_budget_utilization
from app.services.events import emit, handles
from app.services.notify import notify
from app.services.risk_engine import recalculate_department_risk


@handles("carbon.txn.created")
def on_carbon_transaction_created(db: Session, event: DomainEvent) -> None:
    if event.department_id is None:
        return
    activity_date = dt.date.fromisoformat(event.payload["activity_date"])
    emitted_tons = float(event.payload.get("co2e_kg", 0)) / 1000
    budgets = db.scalars(
        select(DepartmentCarbonBudget).where(
            DepartmentCarbonBudget.department_id == event.department_id,
            DepartmentCarbonBudget.start_date <= activity_date,
            DepartmentCarbonBudget.end_date >= activity_date,
        )
    ).all()
    for budget in budgets:
        utilization = get_department_budget_utilization(
            db, event.department_id, budget.start_date, budget.end_date
        )
        actual = utilization["actual_co2e_tons"]
        limit = float(budget.budgeted_co2e_tons)
        if limit > 0 and actual > limit and actual - emitted_tons <= limit:
            emit(
                db,
                "carbon.budget.exceeded",
                department_id=event.department_id,
                entity_type="department_carbon_budget",
                entity_id=budget.id,
                actor_id=event.actor_id,
                payload={"actual_tons": actual, "budgeted_tons": limit},
            )
    recalculate_department_risk(db, event.department_id, actor_id=event.actor_id)


@handles("carbon.budget.exceeded")
def on_carbon_budget_exceeded(db: Session, event: DomainEvent) -> None:
    dept = db.get(Department, event.department_id)
    if dept is None:
        return
    alert = RiskAlert(
        department_id=dept.id,
        risk_score=100.0,
        alert_type="budget_exceeded",
        message=(
            f"Actual emissions {event.payload.get('actual_tons', 0):.3f} tCO2e exceed "
            f"the {event.payload.get('budgeted_tons', 0):.3f} tCO2e budget."
        ),
    )
    db.add(alert)
    db.flush()
    recipients = list(
        db.scalars(
            select(User).where(User.is_active.is_(True), User.role == Role.esg_manager)
        ).all()
    )
    if dept.head is not None:
        recipients.append(dept.head)
    notify(
        db,
        recipients,
        NotificationType.risk_alert,
        f"Carbon budget exceeded: {dept.name}",
        alert.message,
        entity_type="risk_alert",
        entity_id=alert.id,
    )
    emit(
        db,
        "risk.alert.raised",
        department_id=dept.id,
        entity_type="risk_alert",
        entity_id=alert.id,
        actor_id=event.actor_id,
        payload={"alert_type": alert.alert_type, "severity": "critical"},
    )


@handles("compliance.issue.created")
@handles("compliance.issue.status_changed")
def on_compliance_issue_changed(db: Session, event: DomainEvent) -> None:
    if event.department_id is not None:
        recalculate_department_risk(db, event.department_id, actor_id=event.actor_id)
