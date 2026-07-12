import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_esg
from app.db.session import get_db
from app.models.core import User
from app.models.enums import Role, Scope
from app.models.environment import CarbonTransaction
from app.models.scores import DepartmentScoreSnapshot, OrgScoreSnapshot
from app.schemas.scores import (
    DeptScoreDetailOut,
    DeptScoreOut,
    DigitalTwinBreakdownOut,
    DigitalTwinProjectionOut,
    DigitalTwinScenarioIn,
    DigitalTwinScenarioOut,
    OrgScoreOut,
    ScoreTrendPoint,
    WeightsOut,
)
from app.services import score_engine
from app.services.org import managed_dept_ids
from app.services.org_settings import get_org_settings
from app.utils.time import resolve_period

router = APIRouter(tags=["Scores"])


def esg_grade(total: float | None) -> str:
    """Letter band for an ESG score. Higher score = better = safer band."""
    if total is None:
        return "—"
    if total >= 80:
        return "A"
    if total >= 65:
        return "B"
    if total >= 50:
        return "C"
    if total >= 35:
        return "D"
    return "E"


def _dept_out(dept: score_engine.DeptScore) -> DeptScoreOut:
    return DeptScoreOut(**dept.as_dict())


def _org_trend(db: Session, period_type: str = "fy") -> list[ScoreTrendPoint]:
    rows = db.execute(
        select(OrgScoreSnapshot)
        .where(OrgScoreSnapshot.period_type == period_type)
        .order_by(OrgScoreSnapshot.snapshot_date.asc())
    ).scalars().all()
    return [ScoreTrendPoint.model_validate(r) for r in rows]

# --- ESG SCORE ENGINE ENDPOINTS ---


@router.get("/scores/weights", response_model=WeightsOut)
def get_score_weights(
    _current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_org_settings(db)
    return WeightsOut(
        environmental=float(s.weight_env),
        social=float(s.weight_social),
        governance=float(s.weight_gov),
    )


@router.get("/scores/organization", response_model=OrgScoreOut)
def get_organization_score(
    period: str = Query("fy", pattern="^(month|quarter|fy|all)$"),
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    _current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org, start, end = score_engine.compute_period(db, period, date_from, date_to)
    ranked = [_dept_out(d) for d in org.departments]  # already sorted desc by total
    return OrgScoreOut(
        period=period,
        period_start=start,
        period_end=end,
        total=score_engine._r(org.total) if org.dept_count else None,
        grade=esg_grade(org.total if org.dept_count else None),
        environmental=score_engine._r(org.environmental),
        social=score_engine._r(org.social),
        governance=score_engine._r(org.governance),
        dept_count=org.dept_count,
        weights=score_engine._weights(db),
        top_departments=ranked[:3],
        bottom_departments=ranked[-3:][::-1] if len(ranked) > 3 else [],
        trend=_org_trend(db),
    )


@router.get("/scores/departments", response_model=list[DeptScoreOut])
def list_department_scores(
    period: str = Query("fy", pattern="^(month|quarter|fy|all)$"),
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = resolve_period(period, date_from, date_to)
    depts = score_engine.compute_all_departments(db, start, end)
    ordered = sorted(depts.values(), key=lambda d: d.total, reverse=True)
    if current.role not in (Role.admin, Role.esg_manager):
        allowed = managed_dept_ids(db, current)
        if current.department_id is not None:
            allowed = allowed | {current.department_id}
        ordered = [d for d in ordered if d.department_id in allowed]
    return [_dept_out(d) for d in ordered]


@router.get("/scores/departments/{department_id}", response_model=DeptScoreDetailOut)
def get_department_score(
    department_id: int,
    period: str = Query("fy", pattern="^(month|quarter|fy|all)$"),
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.role not in (Role.admin, Role.esg_manager):
        allowed = managed_dept_ids(db, current)
        if current.department_id is not None:
            allowed = allowed | {current.department_id}
        if department_id not in allowed:
            raise HTTPException(status_code=403, detail="Not permitted to view this department")

    start, end = resolve_period(period, date_from, date_to)
    depts = score_engine.compute_all_departments(db, start, end)
    dept = depts.get(department_id)
    if dept is None:
        raise HTTPException(
            status_code=404,
            detail="Department has no active employees to score for this period",
        )
    trend = db.execute(
        select(DepartmentScoreSnapshot)
        .where(
            DepartmentScoreSnapshot.department_id == department_id,
            DepartmentScoreSnapshot.period_type == "fy",
        )
        .order_by(DepartmentScoreSnapshot.snapshot_date.asc())
    ).scalars().all()
    return DeptScoreDetailOut(
        period=period,
        period_start=start,
        period_end=end,
        grade=esg_grade(dept.total),
        department=_dept_out(dept),
        trend=[ScoreTrendPoint.model_validate(r) for r in trend],
    )


@router.post("/scores/recalculate", response_model=OrgScoreOut)
def recalculate_scores(
    period: str = Query("fy", pattern="^(month|quarter|fy|all)$"),
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    """Recompute and snapshot today's scores now (demo insurance)."""
    score_engine.snapshot_scores(db)
    db.commit()
    return get_organization_score(period=period, _current=current, db=db)


DEMO_CARBON_KG = 1_000_000.0
EV_AVOIDED_EMISSIONS_RATE = 0.90
COMMUTING_SHARE_OF_SCOPE3 = 0.25
SUPPLIER_SHARE_OF_SCOPE3 = 0.75
SAVINGS_INR_PER_KG_AVOIDED = 18.0
SCORE_POINTS_PER_REDUCTION_PCT = 0.5


def _round(value: float, digits: int = 1) -> float:
    return round(float(value), digits)


def _ledger_by_scope(
    db: Session, start_date, end_date
) -> tuple[dict[Scope, float], bool]:
    rows = db.execute(
        select(CarbonTransaction.scope, func.sum(CarbonTransaction.co2e_kg))
        .where(
            CarbonTransaction.activity_date >= start_date,
            CarbonTransaction.activity_date <= end_date,
        )
        .group_by(CarbonTransaction.scope)
    ).all()
    totals = {scope: float(value or 0) for scope, value in rows}
    return totals, sum(totals.values()) > 0


def _baseline_by_scope(
    ledger: dict[Scope, float], has_live_data: bool
) -> tuple[float, float, float, float]:
    if has_live_data:
        total = sum(ledger.values())
        scope1 = ledger.get(Scope.scope1, 0.0)
        scope3 = ledger.get(Scope.scope3, 0.0)
        return (
            total,
            scope1,
            scope3 * COMMUTING_SHARE_OF_SCOPE3,
            scope3 * SUPPLIER_SHARE_OF_SCOPE3,
        )
    return DEMO_CARBON_KG, 300_000.0, 100_000.0, 300_000.0


def _simulate(
    payload: DigitalTwinScenarioIn,
    current_carbon_kg: float,
    fleet_baseline_kg: float,
    commute_baseline_kg: float,
    supplier_baseline_kg: float,
) -> tuple[list[DigitalTwinBreakdownOut], float]:
    fleet_reduction = (
        fleet_baseline_kg
        * payload.fleet_electrification_pct
        / 100
        * EV_AVOIDED_EMISSIONS_RATE
    )
    remote_reduction = (
        commute_baseline_kg
        * payload.remote_employee_pct
        / 100
        * payload.remote_days_per_week
        / 5
    )
    supplier_reduction = (
        supplier_baseline_kg
        * payload.supplier_switch_pct
        / 100
        * payload.supplier_emissions_improvement_pct
        / 100
    )
    reductions = [fleet_reduction, remote_reduction, supplier_reduction]
    breakdown = [
        DigitalTwinBreakdownOut(
            key="fleet",
            label="Fleet electrification",
            baseline_carbon_kg=_round(fleet_baseline_kg),
            reduction_kg=_round(fleet_reduction),
            reduction_pct_of_total=_round(fleet_reduction / current_carbon_kg * 100),
            assumption=(
                f"{payload.fleet_electrification_pct:g}% of the fleet transitions to EVs "
                f"at {EV_AVOIDED_EMISSIONS_RATE * 100:g}% avoided tailpipe emissions."
            ),
        ),
        DigitalTwinBreakdownOut(
            key="remote",
            label="Hybrid work",
            baseline_carbon_kg=_round(commute_baseline_kg),
            reduction_kg=_round(remote_reduction),
            reduction_pct_of_total=_round(remote_reduction / current_carbon_kg * 100),
            assumption=(
                f"{payload.remote_employee_pct:g}% of employees work remotely "
                f"{payload.remote_days_per_week:g} day(s) per five-day week."
            ),
        ),
        DigitalTwinBreakdownOut(
            key="supplier",
            label="Supplier transition",
            baseline_carbon_kg=_round(supplier_baseline_kg),
            reduction_kg=_round(supplier_reduction),
            reduction_pct_of_total=_round(supplier_reduction / current_carbon_kg * 100),
            assumption=(
                f"{payload.supplier_switch_pct:g}% of spend moves from {payload.supplier_from} "
                f"to {payload.supplier_to}, which is modeled as "
                f"{payload.supplier_emissions_improvement_pct:g}% lower-carbon."
            ),
        ),
    ]
    return breakdown, min(sum(reductions), current_carbon_kg)


@router.post("/scores/simulate", response_model=DigitalTwinScenarioOut)
def simulate_digital_twin(
    payload: DigitalTwinScenarioIn,
    _current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    start_date, end_date = resolve_period(
        payload.period, payload.date_from, payload.date_to
    )
    # Baseline ESG score is derived server-side from the live scoring engine;
    # the client-supplied current_esg_score is only an advisory fallback used
    # when the organization has no scoreable data yet.
    org = score_engine.compute_org_score(db, start_date, end_date)
    if org.dept_count > 0:
        baseline_score = org.total
        baseline_source = "computed_score"
    else:
        baseline_score = payload.current_esg_score
        baseline_source = "advisory_input"
    ledger, has_live_data = _ledger_by_scope(db, start_date, end_date)
    live_total = sum(ledger.values())
    use_live_baseline = has_live_data and live_total >= DEMO_CARBON_KG
    if use_live_baseline:
        data_source = "live_ledger"
    elif has_live_data:
        data_source = "planning_baseline"
    else:
        data_source = "demo_baseline"
    current_carbon, fleet_baseline, commute_baseline, supplier_baseline = (
        _baseline_by_scope(ledger, use_live_baseline)
    )
    breakdown, reduction = _simulate(
        payload,
        current_carbon,
        fleet_baseline,
        commute_baseline,
        supplier_baseline,
    )
    reduction_pct = reduction / current_carbon * 100
    scenario_carbon = max(current_carbon - reduction, 0)
    scenario_score = min(
        baseline_score + reduction_pct * SCORE_POINTS_PER_REDUCTION_PCT,
        100,
    )
    annual_savings = reduction * SAVINGS_INR_PER_KG_AVOIDED
    projection = [
        DigitalTwinProjectionOut(
            year=label,
            current_carbon_kg=_round(current_carbon),
            scenario_carbon_kg=_round(current_carbon - reduction * adoption),
        )
        for label, adoption in (
            ("Now", 0),
            ("Year 1", 0.45),
            ("Year 3", 0.8),
            ("Year 5", 1),
        )
    ]
    return DigitalTwinScenarioOut(
        data_source=data_source,
        baseline_source=baseline_source,
        period_start=start_date,
        period_end=end_date,
        current_esg_score=_round(baseline_score),
        scenario_esg_score=_round(scenario_score),
        score_uplift=_round(scenario_score - baseline_score),
        current_carbon_kg=_round(current_carbon),
        scenario_carbon_kg=_round(scenario_carbon),
        carbon_reduction_kg=_round(reduction),
        carbon_reduction_pct=_round(reduction_pct),
        annual_savings_inr=_round(annual_savings, 0),
        annual_savings_lakh=_round(annual_savings / 100_000),
        breakdown=breakdown,
        projection=projection,
        methodology=[
            (
                "Baseline ESG score is the live engine-computed organization score."
                if baseline_source == "computed_score"
                else "No scoreable data yet, so the baseline ESG score uses the advisory input value."
            ),
            (
                "The current ledger is below the 1,000-tonne annual completeness threshold, so this run uses the disclosed annual planning baseline."
                if data_source == "planning_baseline"
                else (
                    "The scenario baseline is calculated from the selected-period carbon ledger."
                    if data_source == "live_ledger"
                    else "No ledger data was available, so this run uses the disclosed 1,000-tonne demo baseline."
                )
            ),
            "Fleet baseline uses Scope 1 ledger emissions; EVs avoid 90% of modeled tailpipe emissions.",
            "Scope 3 is split into a 25% commuting pool and 75% supplier pool for scenario modeling.",
            "Estimated annual savings use ₹18 per kgCO₂e avoided; validate with Finance before investment approval.",
            "ESG score uplift is 0.5 points per percentage point of carbon reduction and is capped at 100.",
        ],
    )
