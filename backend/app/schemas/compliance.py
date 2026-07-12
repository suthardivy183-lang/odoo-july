import datetime as dt
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import IssueStatus, Severity


class ComplianceIssueCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: str = ""
    severity: Severity
    owner_user_id: int
    due_date: dt.date
    department_id: int


class ComplianceIssueUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = None
    severity: Severity | None = None
    owner_user_id: int | None = None
    due_date: dt.date | None = None
    status: IssueStatus | None = None
    department_id: int | None = None


class ComplianceIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    severity: Severity
    owner_user_id: int
    owner_name: str | None = None
    due_date: dt.date
    status: IssueStatus
    department_id: int | None
    department_name: str | None = None
    is_overdue: bool
    overdue_notified_at: dt.datetime | None = None
    resolved_at: dt.datetime | None = None
    created_by: int | None
    created_at: dt.datetime
