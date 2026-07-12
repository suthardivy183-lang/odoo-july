import datetime as dt
import enum
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, enum_column


class PricingMethod(str, enum.Enum):
    fixed_internal = "fixed_internal"
    govt_tax = "govt_tax"
    market_credit = "market_credit"


class CarbonPricingRule(TimestampMixin, Base):
    __tablename__ = "carbon_pricing_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    price_per_ton: Mapped[float] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    effective_date: Mapped[dt.date] = mapped_column(Date)
    pricing_method: Mapped[PricingMethod] = mapped_column(enum_column(PricingMethod))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    creator = relationship("User")


class CarbonCostEntry(Base):
    __tablename__ = "carbon_cost_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    carbon_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_transactions.id"), unique=True, index=True
    )
    pricing_rule_id: Mapped[int] = mapped_column(ForeignKey("carbon_pricing_rules.id"))
    co2e_kg: Mapped[float] = mapped_column(Numeric(16, 3))
    price_per_ton_used: Mapped[float] = mapped_column(Numeric(14, 2))
    financial_liability: Mapped[float] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(10))
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    carbon_transaction = relationship(
        "CarbonTransaction", back_populates="carbon_cost_entry"
    )
    pricing_rule = relationship("CarbonPricingRule")


class DepartmentCarbonBudget(TimestampMixin, Base):
    __tablename__ = "department_carbon_budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    fiscal_year: Mapped[str] = mapped_column(String(9))  # e.g., "2026-2027"
    period_type: Mapped[str] = mapped_column(String(10))  # "annual" or "quarterly"
    period_value: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # e.g., "Q1"
    budgeted_co2e_tons: Mapped[float] = mapped_column(Numeric(14, 2))
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date] = mapped_column(Date)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    department = relationship("Department")
    creator = relationship("User")
