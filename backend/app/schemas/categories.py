import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActiveStatus, CategoryType


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: CategoryType
    status: ActiveStatus
    created_at: dt.datetime


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    type: CategoryType
    status: ActiveStatus = ActiveStatus.active


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    status: ActiveStatus | None = None
