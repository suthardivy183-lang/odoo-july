import datetime as dt

from pydantic import BaseModel, Field


class DigitalTwinScenarioIn(BaseModel):
    current_esg_score: float = Field(default=72, ge=0, le=100)
    fleet_electrification_pct: float = Field(default=50, ge=0, le=100)
    remote_employee_pct: float = Field(default=30, ge=0, le=100)
    remote_days_per_week: float = Field(default=2, ge=0, le=5)
    supplier_switch_pct: float = Field(default=30, ge=0, le=100)
    supplier_emissions_improvement_pct: float = Field(default=30, ge=0, le=100)
    supplier_from: str = Field(default="Supplier A", min_length=1, max_length=120)
    supplier_to: str = Field(default="Supplier B", min_length=1, max_length=120)
    period: str = Field(default="fy", pattern="^(month|quarter|fy|all)$")
    date_from: dt.date | None = None
    date_to: dt.date | None = None


class DigitalTwinBreakdownOut(BaseModel):
    key: str
    label: str
    baseline_carbon_kg: float
    reduction_kg: float
    reduction_pct_of_total: float
    assumption: str


class DigitalTwinProjectionOut(BaseModel):
    year: str
    current_carbon_kg: float
    scenario_carbon_kg: float


class DigitalTwinScenarioOut(BaseModel):
    data_source: str
    period_start: dt.date
    period_end: dt.date
    current_esg_score: float
    scenario_esg_score: float
    score_uplift: float
    current_carbon_kg: float
    scenario_carbon_kg: float
    carbon_reduction_kg: float
    carbon_reduction_pct: float
    annual_savings_inr: float
    annual_savings_lakh: float
    breakdown: list[DigitalTwinBreakdownOut]
    projection: list[DigitalTwinProjectionOut]
    methodology: list[str]
