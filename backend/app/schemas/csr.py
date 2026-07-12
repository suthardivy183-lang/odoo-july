import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import CSRStatus, ParticipationStatus
from app.schemas.common import AttachmentOut, UserBrief


class CSRActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category_id: int
    category_name: str | None = None
    location: str
    organizer: UserBrief | None = None
    capacity: int
    start_date: dt.date
    end_date: dt.date
    budget_inr: float | None = None
    points: int
    status: CSRStatus
    created_at: dt.datetime
    joined_count: int = 0
    my_participation_id: int | None = None
    my_participation_status: ParticipationStatus | None = None


class CSRActivityCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    category_id: int
    location: str = Field(min_length=2, max_length=160)
    organizer_user_id: int | None = None
    capacity: int = Field(default=50, ge=1)
    start_date: dt.date
    end_date: dt.date
    budget_inr: float | None = Field(default=None, ge=0)
    points: int = Field(default=50, ge=0)

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self


class CSRActivityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    category_id: int | None = None
    location: str | None = Field(default=None, min_length=2, max_length=160)
    organizer_user_id: int | None = None
    capacity: int | None = Field(default=None, ge=1)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    budget_inr: float | None = Field(default=None, ge=0)
    points: int | None = Field(default=None, ge=0)


class CSRStatusIn(BaseModel):
    status: CSRStatus


class ProofIn(BaseModel):
    attachment_id: int


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject", "resubmit"]
    comment: str = ""

    @model_validator(mode="after")
    def comment_required(self):
        if self.decision in ("reject", "resubmit") and not self.comment.strip():
            raise ValueError("A comment is required when rejecting or requesting resubmission")
        return self


class CSRParticipationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activity_id: int
    activity_title: str | None = None
    activity_points: int | None = None
    user: UserBrief
    status: ParticipationStatus
    proof: AttachmentOut | None = None
    points_earned: int | None = None
    completion_date: dt.date | None = None
    approver: UserBrief | None = None
    decided_at: dt.datetime | None = None
    approver_comment: str | None = None
    created_at: dt.datetime
