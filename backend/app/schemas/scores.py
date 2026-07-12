import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


# --- ESG score engine ---


class ScoreComponentOut(BaseModel):
    key: str
    label: str
    value: float | None
    inputs: dict


class DeptScoreOut(BaseModel):
    department_id: int
    department_name: str
    employee_count: int
    environmental: float | None
    social: float | None
    governance: float | None
    total: float | None
    components: list[ScoreComponentOut] = []


class ScoreTrendPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_date: dt.date
    total_score: float
    environmental_score: float | None
    social_score: float | None
    governance_score: float | None


class OrgScoreOut(BaseModel):
    period: str
    period_start: dt.date
    period_end: dt.date
    total: float | None
    grade: str
    environmental: float | None
    social: float | None
    governance: float | None
    dept_count: int
    weights: dict
    top_departments: list[DeptScoreOut]
    bottom_departments: list[DeptScoreOut]
    trend: list[ScoreTrendPoint]


class WeightsOut(BaseModel):
    environmental: float
    social: float
    governance: float


class DeptScoreDetailOut(BaseModel):
    period: str
    period_start: dt.date
    period_end: dt.date
    grade: str
    department: DeptScoreOut
    trend: list[ScoreTrendPoint]


class DigitalTwinScenarioIn(BaseModel):
    # Advisory only: the server prefers the live computed ESG score as the
    # baseline and ignores this whenever scoreable data exists (see /simulate).
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
    baseline_source: str
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
