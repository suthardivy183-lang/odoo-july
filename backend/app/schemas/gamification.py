import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.enums import RedemptionStatus, XPType
from app.schemas.common import UserBrief


class XPSummaryOut(BaseModel):
    xp_balance: int
    lifetime_earned: int
    approved_challenges: int
    approved_csr: int
    badges_count: int


class XPTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: int
    type: XPType
    ref_type: str | None = None
    ref_id: int | None = None
    description: str
    balance_after: int
    created_at: dt.datetime


class LeaderboardEntry(BaseModel):
    rank: int
    user: UserBrief
    department_name: str | None = None
    xp: int


class LeaderboardOut(BaseModel):
    period: Literal["weekly", "monthly", "all"]
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    entries: list[LeaderboardEntry]
    my_rank: int | None = None
    my_xp: int = 0


class RedeemIn(BaseModel):
    reward_id: int


class RedemptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reward_id: int
    reward_name: str | None = None
    user: UserBrief
    points_spent: int
    status: RedemptionStatus
    created_at: dt.datetime
    updated_at: dt.datetime
