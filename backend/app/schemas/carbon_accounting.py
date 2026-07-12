import datetime as dt
from pydantic import BaseModel, ConfigDict, Field
from app.models.carbon_accounting import PricingMethod


class PricingRuleCreate(BaseModel):
    price_per_ton: float = Field(..., gt=0)
    currency: str = Field("INR", max_length=10)
    effective_date: dt.date
    pricing_method: PricingMethod
    is_active: bool = False


class PricingRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price_per_ton: float
    currency: str
    effective_date: dt.date
    pricing_method: PricingMethod
    is_active: bool
    version: int
    created_at: dt.datetime


class CarbonCostEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    carbon_transaction_id: int
    pricing_rule_id: int
    co2e_kg: float
    price_per_ton_used: float
    financial_liability: float
    currency: str
    timestamp: dt.datetime


class CarbonTransactionCreate(BaseModel):
    department_id: int
    activity_date: dt.date
    description: str = Field(..., max_length=255)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., max_length=20)
    emission_factor_id: int
    notes: str | None = None


class CarbonTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: int
    department_name: str | None = None
    activity_date: dt.date
    description: str
    quantity: float
    unit: str
    emission_factor_id: int
    factor_value_snapshot: float
    factor_version_snapshot: int
    co2e_kg: float
    scope: str
    is_auto: bool
    notes: str | None = None
    created_at: dt.datetime
    carbon_cost_entry: CarbonCostEntryOut | None = None


class CarbonBudgetCreate(BaseModel):
    department_id: int
    fiscal_year: str = Field(..., max_length=9)  # e.g., "2026-2027"
    period_type: str = Field("annual", max_length=10)  # "annual" or "quarterly"
    period_value: str | None = Field(None, max_length=10)  # "Q1", "Q2", etc.
    budgeted_co2e_tons: float = Field(..., gt=0)
    start_date: dt.date
    end_date: dt.date


class CarbonBudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: int
    department_name: str | None = None
    fiscal_year: str
    period_type: str
    period_value: str | None = None
    budgeted_co2e_tons: float
    start_date: dt.date
    end_date: dt.date
    actual_co2e_tons: float = 0.0
    budget_utilization_pct: float = 0.0
    estimated_liability: float = 0.0


class SimulationInput(BaseModel):
    diesel_reduction_pct: float = Field(0.0, ge=0.0, le=100.0)
    fleet_ev_pct: float = Field(0.0, ge=0.0, le=100.0)
    solar_replacement_pct: float = Field(0.0, ge=0.0, le=100.0)


class SimulationOutput(BaseModel):
    carbon_reduction_tons: float
    carbon_reduction_pct: float
    financial_savings: float
    new_carbon_liability: float
    esg_score_improvement: float
