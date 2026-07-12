import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActiveStatus


class RewardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    points_cost: int
    stock: int
    status: ActiveStatus
    created_at: dt.datetime
    redeemed_count: int = 0


class RewardCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str = ""
    points_cost: int = Field(ge=1)
    stock: int = Field(default=0, ge=0)
    status: ActiveStatus = ActiveStatus.active


class RewardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    points_cost: int | None = Field(default=None, ge=1)
    stock: int | None = Field(default=None, ge=0)
    status: ActiveStatus | None = None
