import csv
import datetime as dt
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin, require_esg, require_head
from app.db.session import get_db
from app.models.carbon_accounting import (
    CarbonCostEntry,
    CarbonPricingRule,
    DepartmentCarbonBudget,
    PricingMethod,
)
from app.models.core import Department, User
from app.models.enums import ActiveStatus, AuditAction, Role, Scope
from app.models.environment import CarbonTransaction
from app.models.masterdata import EmissionFactor, Product
from app.schemas.carbon_accounting import (
    CarbonBudgetCreate,
    CarbonBudgetOut,
    CarbonTransactionCreate,
    CarbonTransactionOut,
    PricingRuleCreate,
    PricingRuleOut,
    SimulationInput,
    SimulationOutput,
)
from app.schemas.common import Msg, Page
from app.services.audit import log_action, snapshot
from app.services.carbon_accounting import (
    calculate_and_create_carbon_cost,
    get_active_pricing_rule,
    get_department_budget_utilization,
)

# PDF and Excel imports
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import openpyxl

router = APIRouter(tags=["Carbon"])


# --- PRICING RULES ENDPOINTS ---


@router.post("/carbon/pricing-rules", response_model=PricingRuleOut)
def create_pricing_rule(
    payload: PricingRuleCreate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    # Find latest version
    max_ver = db.execute(select(func.max(CarbonPricingRule.version))).scalar() or 0

    rule = CarbonPricingRule(
        price_per_ton=payload.price_per_ton,
        currency=payload.currency,
        effective_date=payload.effective_date,
        pricing_method=payload.pricing_method,
        is_active=payload.is_active,
        version=max_ver + 1,
        created_by=current.id,
    )
    db.add(rule)
    db.flush()

    if rule.is_active:
        # Deactivate all other rules
        db.execute(
            CarbonPricingRule.__table__.update()
            .where(CarbonPricingRule.id != rule.id)
            .values(is_active=False)
        )
        db.flush()

    log_action(
        db,
        current.id,
        AuditAction.create,
        "CarbonPricingRule",
        rule.id,
        f"Version {rule.version}",
        after=snapshot(
            rule, ["price_per_ton", "currency", "pricing_method", "is_active"]
        ),
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/carbon/pricing-rules", response_model=Page[PricingRuleOut])
def list_pricing_rules(
    page: int = 1,
    size: int = Query(20, le=100),
    current: User = Depends(require_head),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * size
    query = select(CarbonPricingRule).order_by(CarbonPricingRule.version.desc())

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = db.execute(query.offset(offset).limit(size)).scalars().all()

    return Page[PricingRuleOut](items=items, total=total)


@router.get("/carbon/pricing-rules/active", response_model=PricingRuleOut)
def get_active_rule_endpoint(db: Session = Depends(get_db)):
    rule = get_active_pricing_rule(db)
    if rule is None:
        raise HTTPException(
            status_code=404, detail="No active carbon pricing rule found"
        )
    return rule


@router.patch("/carbon/pricing-rules/{rule_id}/activate", response_model=PricingRuleOut)
def activate_pricing_rule(
    rule_id: int,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    rule = db.get(CarbonPricingRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Pricing rule not found")

    before = snapshot(rule, ["is_active"])

    rule.is_active = True
    db.flush()

    # Deactivate all other rules
    db.execute(
        CarbonPricingRule.__table__.update()
        .where(CarbonPricingRule.id != rule.id)
        .values(is_active=False)
    )
    db.flush()

    log_action(
        db,
        current.id,
        AuditAction.update,
        "CarbonPricingRule",
        rule.id,
        f"Version {rule.version}",
        before=before,
        after=snapshot(rule, ["is_active"]),
    )
    db.commit()
    db.refresh(rule)
    return rule


# --- DEPARTMENT BUDGETS ENDPOINTS ---


@router.post("/carbon/budgets", response_model=CarbonBudgetOut)
def create_or_update_budget(
    payload: CarbonBudgetCreate,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    dept = db.get(Department, payload.department_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")

    # Check if budget exists for department + fiscal year + period type + period value
    existing = db.execute(
        select(DepartmentCarbonBudget).where(
            DepartmentCarbonBudget.department_id == payload.department_id,
            DepartmentCarbonBudget.fiscal_year == payload.fiscal_year,
            DepartmentCarbonBudget.period_type == payload.period_type,
            DepartmentCarbonBudget.period_value == payload.period_value,
        )
    ).scalar_one_or_none()

    if existing:
        before = snapshot(existing, ["budgeted_co2e_tons", "start_date", "end_date"])
        existing.budgeted_co2e_tons = payload.budgeted_co2e_tons
        existing.start_date = payload.start_date
        existing.end_date = payload.end_date
        db.flush()
        log_action(
            db,
            current.id,
            AuditAction.update,
            "DepartmentCarbonBudget",
            existing.id,
            f"{dept.name} budget {payload.fiscal_year}",
            before=before,
            after=snapshot(existing, ["budgeted_co2e_tons", "start_date", "end_date"]),
        )
        budget = existing
    else:
        budget = DepartmentCarbonBudget(
            department_id=payload.department_id,
            fiscal_year=payload.fiscal_year,
            period_type=payload.period_type,
            period_value=payload.period_value,
            budgeted_co2e_tons=payload.budgeted_co2e_tons,
            start_date=payload.start_date,
            end_date=payload.end_date,
            created_by=current.id,
        )
        db.add(budget)
        db.flush()
        log_action(
            db,
            current.id,
            AuditAction.create,
            "DepartmentCarbonBudget",
            budget.id,
            f"{dept.name} budget {payload.fiscal_year}",
            after=snapshot(budget, ["budgeted_co2e_tons", "start_date", "end_date"]),
        )

    db.commit()
    db.refresh(budget)

    # Return with computed values
    util = get_department_budget_utilization(
        db, budget.department_id, budget.start_date, budget.end_date
    )
    out = CarbonBudgetOut.model_validate(budget)
    out.department_name = dept.name
    out.actual_co2e_tons = util["actual_co2e_tons"]
    out.estimated_liability = util["actual_liability"]
    out.budget_utilization_pct = (
        round(out.actual_co2e_tons / out.budgeted_co2e_tons * 100.0, 1)
        if out.budgeted_co2e_tons > 0
        else 0.0
    )
    return out


@router.get("/carbon/budgets", response_model=Page[CarbonBudgetOut])
def list_budgets(
    department_id: int | None = None,
    fiscal_year: str | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(DepartmentCarbonBudget)
    if department_id is not None:
        query = query.where(DepartmentCarbonBudget.department_id == department_id)
    if fiscal_year is not None:
        query = query.where(DepartmentCarbonBudget.fiscal_year == fiscal_year)

    budgets = db.execute(query).scalars().all()

    out_items = []
    for b in budgets:
        util = get_department_budget_utilization(
            db, b.department_id, b.start_date, b.end_date
        )
        out = CarbonBudgetOut.model_validate(b)
        out.department_name = b.department.name if b.department else None
        out.actual_co2e_tons = util["actual_co2e_tons"]
        out.estimated_liability = util["actual_liability"]
        out.budget_utilization_pct = (
            round(out.actual_co2e_tons / out.budgeted_co2e_tons * 100.0, 1)
            if out.budgeted_co2e_tons > 0
            else 0.0
        )
        out_items.append(out)

    return Page[CarbonBudgetOut](items=out_items, total=len(out_items))


# --- MANUAL CARBON TRANSACTIONS ---


@router.post("/carbon/transactions", response_model=CarbonTransactionOut)
def create_carbon_transaction(
    payload: CarbonTransactionCreate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    dept = db.get(Department, payload.department_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    if dept.status != ActiveStatus.active:
        raise HTTPException(
            status_code=400,
            detail="Cannot assign transaction to an inactive department",
        )

    factor = db.get(EmissionFactor, payload.emission_factor_id)
    if factor is None:
        raise HTTPException(status_code=404, detail="Emission factor not found")

    co2e_kg = payload.quantity * float(factor.factor_value)

    tx = CarbonTransaction(
        department_id=payload.department_id,
        activity_date=payload.activity_date,
        description=payload.description,
        quantity=payload.quantity,
        unit=payload.unit,
        emission_factor_id=payload.emission_factor_id,
        factor_value_snapshot=factor.factor_value,
        factor_version_snapshot=factor.version,
        co2e_kg=co2e_kg,
        scope=factor.scope,
        is_auto=False,
        notes=payload.notes,
        created_by=current.id,
    )
    db.add(tx)
    db.flush()

    # Create Cost Entry
    calculate_and_create_carbon_cost(db, tx)
    db.flush()

    log_action(
        db,
        current.id,
        AuditAction.create,
        "CarbonTransaction",
        tx.id,
        tx.description,
        after=snapshot(tx, ["co2e_kg", "scope", "quantity"]),
    )

    db.commit()
    db.refresh(tx)

    # Return output schema
    out = CarbonTransactionOut.model_validate(tx)
    out.department_name = dept.name
    return out


@router.get("/carbon/transactions", response_model=Page[CarbonTransactionOut])
def list_carbon_transactions(
    page: int = 1,
    size: int = Query(20, le=100),
    department_id: int | None = None,
    scope: Scope | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * size
    query = (
        select(CarbonTransaction)
        .options(selectinload(CarbonTransaction.carbon_cost_entry))
        .order_by(CarbonTransaction.activity_date.desc(), CarbonTransaction.id.desc())
    )

    if department_id is not None:
        query = query.where(CarbonTransaction.department_id == department_id)
    if scope is not None:
        query = query.where(CarbonTransaction.scope == scope)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = db.execute(query.offset(offset).limit(size)).scalars().all()

    dept_names = {d.id: d.name for d in db.execute(select(Department)).scalars().all()}

    out_items = []
    for tx in items:
        out = CarbonTransactionOut.model_validate(tx)
        out.department_name = dept_names.get(tx.department_id)
        out_items.append(out)

    return Page[CarbonTransactionOut](items=out_items, total=total)


# --- CARBON ACCOUNTING DASHBOARD ---


@router.get("/carbon/accounting/dashboard")
def get_accounting_dashboard(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Total Liability and Emissions
    total_emissions_kg = (
        db.execute(select(func.sum(CarbonTransaction.co2e_kg))).scalar() or 0.0
    )
    total_liability = (
        db.execute(select(func.sum(CarbonCostEntry.financial_liability))).scalar()
        or 0.0
    )

    # Monthly Trend (Past 6 months)
    today = dt.date.today()
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
        start_date = dt.date(y, m, 1)
        if m == 12:
            end_date = dt.date(y + 1, 1, 1) - dt.timedelta(days=1)
        else:
            end_date = dt.date(y, m + 1, 1) - dt.timedelta(days=1)

        m_emissions = (
            db.execute(
                select(func.sum(CarbonTransaction.co2e_kg)).where(
                    CarbonTransaction.activity_date >= start_date,
                    CarbonTransaction.activity_date <= end_date,
                )
            ).scalar()
            or 0.0
        )

        m_liability = (
            db.execute(
                select(func.sum(CarbonCostEntry.financial_liability))
                .join(
                    CarbonTransaction,
                    CarbonCostEntry.carbon_transaction_id == CarbonTransaction.id,
                )
                .where(
                    CarbonTransaction.activity_date >= start_date,
                    CarbonTransaction.activity_date <= end_date,
                )
            ).scalar()
            or 0.0
        )

        trend.append(
            {
                "month": f"{y:04d}-{m:02d}",
                "emissions_tons": round(float(m_emissions) / 1000.0, 2),
                "liability": round(float(m_liability), 2),
            }
        )

    # Highest Cost Departments
    depts_data = db.execute(
        select(
            Department.name,
            func.sum(CarbonTransaction.co2e_kg).label("emissions"),
            func.sum(CarbonCostEntry.financial_liability).label("liability"),
        )
        .join(CarbonTransaction, Department.id == CarbonTransaction.department_id)
        .join(
            CarbonCostEntry,
            CarbonTransaction.id == CarbonCostEntry.carbon_transaction_id,
        )
        .group_by(Department.name)
        .order_by(func.sum(CarbonCostEntry.financial_liability).desc())
        .limit(5)
    ).all()

    highest_depts = [
        {
            "name": name,
            "emissions_tons": round(float(emissions) / 1000.0, 2),
            "liability": round(float(liability), 2),
        }
        for name, emissions, liability in depts_data
    ]

    # Top Emission Sources
    sources_data = db.execute(
        select(
            EmissionFactor.name,
            func.sum(CarbonTransaction.co2e_kg).label("emissions"),
            func.sum(CarbonCostEntry.financial_liability).label("liability"),
        )
        .join(
            CarbonTransaction, EmissionFactor.id == CarbonTransaction.emission_factor_id
        )
        .join(
            CarbonCostEntry,
            CarbonTransaction.id == CarbonCostEntry.carbon_transaction_id,
        )
        .group_by(EmissionFactor.name)
        .order_by(func.sum(CarbonTransaction.co2e_kg).desc())
        .limit(5)
    ).all()

    top_sources = [
        {
            "source": name,
            "emissions_tons": round(float(emissions) / 1000.0, 2),
            "liability": round(float(liability), 2),
        }
        for name, emissions, liability in sources_data
    ]

    # Metrics per employee
    headcount = (
        db.execute(select(func.count(User.id)).where(User.is_active.is_(True))).scalar()
        or 1
    )
    cost_per_employee = float(total_liability) / headcount

    # Metrics per product (Mock or aggregated average)
    products_count = db.execute(select(func.count(Product.id))).scalar() or 1
    cost_per_product = float(total_liability) / products_count

    return {
        "total_emissions_tons": round(float(total_emissions_kg) / 1000.0, 2),
        "total_liability": round(float(total_liability), 2),
        "cost_per_employee": round(cost_per_employee, 2),
        "cost_per_product": round(cost_per_product, 2),
        "monthly_trend": trend,
        "highest_cost_departments": highest_depts,
        "top_emission_sources": top_sources,
    }


# --- SCENARIO SIMULATION ---


@router.post("/carbon/accounting/simulate", response_model=SimulationOutput)
def simulate_accounting_scenarios(
    payload: SimulationInput,
    db: Session = Depends(get_db),
):
    # Retrieve baseline emissions
    # Baseline is total emissions in the last 12 months, grouped by categories (diesel, fleet, electricity)
    today = dt.date.today()
    one_year_ago = today - dt.timedelta(days=365)

    all_txs = db.execute(
        select(CarbonTransaction.description, CarbonTransaction.co2e_kg).where(
            CarbonTransaction.activity_date >= one_year_ago
        )
    ).all()

    diesel_baseline = 0.0
    fleet_baseline = 0.0
    solar_baseline = 0.0
    other_baseline = 0.0

    for desc, co2e in all_txs:
        desc_lower = desc.lower()
        if "diesel" in desc_lower or "petrol" in desc_lower:
            diesel_baseline += float(co2e)
        elif "fleet" in desc_lower or "road" in desc_lower or "freight" in desc_lower:
            fleet_baseline += float(co2e)
        elif (
            "electricity" in desc_lower or "grid" in desc_lower or "power" in desc_lower
        ):
            solar_baseline += float(co2e)
        else:
            other_baseline += float(co2e)

    total_baseline = diesel_baseline + fleet_baseline + solar_baseline + other_baseline

    # Reductions
    # 1. Diesel reduction
    diesel_saved = diesel_baseline * (payload.diesel_reduction_pct / 100.0)

    # 2. Fleet EV: 50% EV conversion saves 85% of emissions of those converted vehicles
    fleet_saved = fleet_baseline * (payload.fleet_ev_pct / 100.0) * 0.85

    # 3. Solar replacement
    solar_saved = solar_baseline * (payload.solar_replacement_pct / 100.0)

    total_saved_kg = diesel_saved + fleet_saved + solar_saved
    total_saved_tons = total_saved_kg / 1000.0

    rule = get_active_pricing_rule(db)
    price_per_ton = float(rule.price_per_ton) if rule else 3500.0
    financial_savings = total_saved_tons * price_per_ton

    current_liability_kg = (
        db.execute(select(func.sum(CarbonTransaction.co2e_kg))).scalar() or 0.0
    )
    new_liability = max(
        0.0, (float(current_liability_kg) - total_saved_kg) / 1000.0 * price_per_ton
    )

    reduction_pct = (
        (total_saved_kg / total_baseline * 100.0) if total_baseline > 0 else 0.0
    )

    # ESG Score Improvement
    # Environmental score is out of 100, which contributes 40% (weight_env) to department score.
    # A 10% reduction in carbon emissions would improve the E score by roughly 10% * 0.5 = 5 points.
    esg_improvement = (
        reduction_pct * 0.15
    )  # E.g. 20% reduction leads to 3 point overall ESG score improvement

    return SimulationOutput(
        carbon_reduction_tons=round(total_saved_tons, 2),
        carbon_reduction_pct=round(reduction_pct, 1),
        financial_savings=round(financial_savings, 2),
        new_carbon_liability=round(new_liability, 2),
        esg_score_improvement=round(esg_improvement, 1),
    )


# --- REPORTS GENERATION ---


@router.get("/carbon/accounting/reports")
def export_accounting_reports(
    report_type: str,  # "monthly_cost" | "department_liability" | "budget_utilization"
    file_format: str,  # "pdf" | "excel" | "csv"
    db: Session = Depends(get_db),
):
    if report_type not in [
        "monthly_cost",
        "department_liability",
        "budget_utilization",
    ]:
        raise HTTPException(status_code=400, detail="Invalid report type")
    if file_format not in ["pdf", "excel", "csv"]:
        raise HTTPException(status_code=400, detail="Invalid file format")

    pricing_rule = get_active_pricing_rule(db)
    pricing_str = (
        f"Active Carbon Price: {pricing_rule.currency} {pricing_rule.price_per_ton}/Ton"
        if pricing_rule
        else "No active pricing rule"
    )

    # Gather Data
    if report_type == "monthly_cost":
        headers = ["Month", "Emissions (Tons)", "Financial Liability"]
        # Aggregated past 12 months
        today = dt.date.today()
        months = []
        year, month = today.year, today.month
        for _ in range(12):
            months.append((year, month))
            month -= 1
            if month == 0:
                year, month = year - 1, 12
        months.reverse()

        rows = []
        for y, m in months:
            start_date = dt.date(y, m, 1)
            if m == 12:
                end_date = dt.date(y + 1, 1, 1) - dt.timedelta(days=1)
            else:
                end_date = dt.date(y, m + 1, 1) - dt.timedelta(days=1)

            m_emissions = (
                db.execute(
                    select(func.sum(CarbonTransaction.co2e_kg)).where(
                        CarbonTransaction.activity_date >= start_date,
                        CarbonTransaction.activity_date <= end_date,
                    )
                ).scalar()
                or 0.0
            )

            m_liability = (
                db.execute(
                    select(func.sum(CarbonCostEntry.financial_liability))
                    .join(
                        CarbonTransaction,
                        CarbonCostEntry.carbon_transaction_id == CarbonTransaction.id,
                    )
                    .where(
                        CarbonTransaction.activity_date >= start_date,
                        CarbonTransaction.activity_date <= end_date,
                    )
                ).scalar()
                or 0.0
            )

            rows.append(
                [
                    f"{y:04d}-{m:02d}",
                    round(float(m_emissions) / 1000.0, 2),
                    round(float(m_liability), 2),
                ]
            )
        title = "Monthly Carbon Cost Report"

    elif report_type == "department_liability":
        headers = ["Department", "Emissions (Tons)", "Financial Liability"]
        data_rows = db.execute(
            select(
                Department.name,
                func.sum(CarbonTransaction.co2e_kg).label("emissions"),
                func.sum(CarbonCostEntry.financial_liability).label("liability"),
            )
            .join(CarbonTransaction, Department.id == CarbonTransaction.department_id)
            .join(
                CarbonCostEntry,
                CarbonTransaction.id == CarbonCostEntry.carbon_transaction_id,
            )
            .group_by(Department.name)
            .order_by(func.sum(CarbonCostEntry.financial_liability).desc())
        ).all()

        rows = [
            [name, round(float(emissions) / 1000.0, 2), round(float(liability), 2)]
            for name, emissions, liability in data_rows
        ]
        title = "Department Carbon Liability Report"

    else:  # budget_utilization
        headers = [
            "Department",
            "Fiscal Year",
            "Budget (Tons)",
            "Actual (Tons)",
            "Util %",
            "Liability",
        ]
        budgets = db.execute(select(DepartmentCarbonBudget)).scalars().all()

        rows = []
        for b in budgets:
            util = get_department_budget_utilization(
                db, b.department_id, b.start_date, b.end_date
            )
            act_tons = util["actual_co2e_tons"]
            util_pct = (
                round(act_tons / b.budgeted_co2e_tons * 100.0, 1)
                if b.budgeted_co2e_tons > 0
                else 0.0
            )

            rows.append(
                [
                    b.department.name if b.department else "Unknown",
                    b.fiscal_year,
                    b.budgeted_co2e_tons,
                    round(act_tons, 2),
                    util_pct,
                    round(util["actual_liability"], 2),
                ]
            )
        title = "Carbon Budget Utilization Report"

    # Render format
    if file_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([title])
        writer.writerow([pricing_str])
        writer.writerow([])
        writer.writerow(headers)
        writer.writerows(rows)

        response = Response(content=output.getvalue(), media_type="text/csv")
        response.headers["Content-Disposition"] = (
            f"attachment; filename={report_type}.csv"
        )
        return response

    elif file_format == "excel":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Report"

        ws.append([title])
        ws.append([pricing_str])
        ws.append([])
        ws.append(headers)
        for r in rows:
            ws.append(r)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response.headers["Content-Disposition"] = (
            f"attachment; filename={report_type}.xlsx"
        )
        return response

    else:  # pdf
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()

        # Define styles
        title_style = ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1b4332"),
            spaceAfter=15,
        )
        meta_style = ParagraphStyle(
            name="ReportMeta",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#495057"),
            spaceAfter=30,
        )

        elements = [
            Paragraph(title, title_style),
            Paragraph(pricing_str, meta_style),
            Spacer(1, 15),
        ]

        # Add table
        table_data = [headers] + rows
        t = Table(table_data)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b4332")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#dee2e6")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(t)
        doc.build(elements)

        pdf_buffer.seek(0)
        response = StreamingResponse(pdf_buffer, media_type="application/pdf")
        response.headers["Content-Disposition"] = (
            f"attachment; filename={report_type}.pdf"
        )
        return response
