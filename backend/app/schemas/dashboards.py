import datetime as dt

from pydantic import BaseModel

from app.schemas.common import UserBrief


class EmployeeDashboardOut(BaseModel):
    xp_balance: int
    lifetime_earned: int
    my_rank: int | None = None
    badges_count: int
    active_challenge_participations: int
    approved_challenges: int
    csr_participations: int
    approved_csr: int
    pending_policy_acks: int
    unread_notifications: int
    active_challenges_open: int
    active_csr_open: int


class GenderSlice(BaseModel):
    gender: str
    count: int


class MonthlyEngagement(BaseModel):
    month: str  # YYYY-MM
    csr: int
    challenges: int


class TopPerformer(BaseModel):
    user: UserBrief
    department_name: str | None = None
    xp_balance: int


class HeadDashboardOut(BaseModel):
    department_ids: list[int]
    headcount: int
    pending_csr_approvals: int
    pending_challenge_approvals: int
    csr_participation_rate: float  # 0-100, distinct employees with approved CSR
    challenge_completion_rate: float  # 0-100, distinct employees with approved challenge
    gender_distribution: list[GenderSlice]
    engagement_trend: list[MonthlyEngagement]
    top_performers: list[TopPerformer]
    as_of: dt.date
