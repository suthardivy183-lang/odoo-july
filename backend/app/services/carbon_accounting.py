import datetime as dt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.carbon_accounting import CarbonCostEntry, CarbonPricingRule, DepartmentCarbonBudget
from app.models.environment import CarbonTransaction


def get_active_pricing_rule(db: Session) -> CarbonPricingRule | None:
    """Retrieve the currently active carbon pricing rule."""
    return db.execute(
        select(CarbonPricingRule).where(CarbonPricingRule.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()


def calculate_and_create_carbon_cost(
    db: Session, tx: CarbonTransaction
) -> CarbonCostEntry | None:
    """Calculate the carbon cost for a transaction using the active pricing rule."""
    rule = get_active_pricing_rule(db)
    if rule is None:
        return None

    # Check if a cost entry already exists
    existing = db.execute(
        select(CarbonCostEntry).where(CarbonCostEntry.carbon_transaction_id == tx.id)
    ).scalar_one_or_none()

    co2e_tons = float(tx.co2e_kg) / 1000.0
    price = float(rule.price_per_ton)
    liability = round(co2e_tons * price, 2)

    if existing:
        existing.pricing_rule_id = rule.id
        existing.co2e_kg = tx.co2e_kg
        existing.price_per_ton_used = rule.price_per_ton
        existing.financial_liability = liability
        existing.currency = rule.currency
        return existing

    entry = CarbonCostEntry(
        carbon_transaction_id=tx.id,
        pricing_rule_id=rule.id,
        co2e_kg=tx.co2e_kg,
        price_per_ton_used=rule.price_per_ton,
        financial_liability=liability,
        currency=rule.currency,
    )
    db.add(entry)
    db.flush()
    return entry


def get_department_budget_utilization(
    db: Session, department_id: int, start_date: dt.date, end_date: dt.date
) -> dict:
    """Calculate actual emissions and liability for a department in a date range."""
    # We include all sub-departments or just the department?
    # Usually, a budget is for the department itself.
    # Let's aggregate for the department itself first.
    emissions_sum = db.execute(
        select(func.sum(CarbonTransaction.co2e_kg))
        .where(
            CarbonTransaction.department_id == department_id,
            CarbonTransaction.activity_date >= start_date,
            CarbonTransaction.activity_date <= end_date,
        )
    ).scalar_one() or 0.0

    liability_sum = db.execute(
        select(func.sum(CarbonCostEntry.financial_liability))
        .join(CarbonTransaction, CarbonCostEntry.carbon_transaction_id == CarbonTransaction.id)
        .where(
            CarbonTransaction.department_id == department_id,
            CarbonTransaction.activity_date >= start_date,
            CarbonTransaction.activity_date <= end_date,
        )
    ).scalar_one() or 0.0

    return {
        "actual_co2e_kg": float(emissions_sum),
        "actual_co2e_tons": float(emissions_sum) / 1000.0,
        "actual_liability": float(liability_sum),
    }
