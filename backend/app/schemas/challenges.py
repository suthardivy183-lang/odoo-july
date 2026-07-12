import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ChallengeStatus,
    Difficulty,
    EvidenceMode,
    ParticipationStatus,
)
from app.schemas.common import AttachmentOut, UserBrief


class ChallengeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category_id: int
    category_name: str | None = None
    description: str
    xp: int
    difficulty: Difficulty
    evidence: EvidenceMode
    deadline: dt.date
    status: ChallengeStatus
    created_at: dt.datetime
    participant_count: int = 0
    my_participation_id: int | None = None
    my_participation_status: ParticipationStatus | None = None
    my_progress: int | None = None


class ChallengeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category_id: int
    description: str = ""
    xp: int = Field(ge=1)
    difficulty: Difficulty
    evidence: EvidenceMode = EvidenceMode.inherit
    deadline: dt.date


class ChallengeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    category_id: int | None = None
    description: str | None = None
    xp: int | None = Field(default=None, ge=1)
    difficulty: Difficulty | None = None
    evidence: EvidenceMode | None = None
    deadline: dt.date | None = None


class ChallengeStatusIn(BaseModel):
    status: ChallengeStatus


class ProgressIn(BaseModel):
    progress: int = Field(ge=0, le=100)


class ChallengeParticipationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    challenge_id: int
    challenge_title: str | None = None
    challenge_xp: int | None = None
    challenge_evidence: EvidenceMode | None = None
    user: UserBrief
    progress: int
    status: ParticipationStatus
    proof: AttachmentOut | None = None
    xp_awarded: int | None = None
    completion_date: dt.date | None = None
    approver: UserBrief | None = None
    decided_at: dt.datetime | None = None
    approver_comment: str | None = None
    created_at: dt.datetime
