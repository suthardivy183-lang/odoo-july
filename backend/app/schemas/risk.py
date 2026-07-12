import datetime as dt
from pydantic import BaseModel, ConfigDict


class DepartmentRiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: int
    department_name: str | None = None
    environmental_risk: float
    social_risk: float
    governance_risk: float
    overall_risk: float


class RiskAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: int
    department_name: str | None = None
    risk_score: float
    alert_type: str
    message: str
    timestamp: dt.datetime


class DrillDownOut(BaseModel):
    overall_risk: float
    environmental_risk: float
    social_risk: float
    governance_risk: float
    contributors: list[str]
    recommendations: list[str]
    ai_insight: str
