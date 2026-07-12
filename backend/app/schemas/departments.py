import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ActiveStatus
from app.schemas.common import UserBrief


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    head_user_id: int | None = None
    parent_id: int | None = None
    status: ActiveStatus = ActiveStatus.active

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Department name cannot be blank")
        return value


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    head_user_id: int | None = None
    parent_id: int | None = None
    status: ActiveStatus | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Department name cannot be blank")
        return value


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    head_user_id: int | None = None
    head: UserBrief | None = None
    parent_id: int | None = None
    status: ActiveStatus
    direct_employee_count: int = 0
    total_employee_count: int = 0
    created_at: dt.datetime
    updated_at: dt.datetime


class DepartmentTreeOut(DepartmentOut):
    children: list["DepartmentTreeOut"] = Field(default_factory=list)
