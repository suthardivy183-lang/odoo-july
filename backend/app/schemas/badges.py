import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ActiveStatus, BadgeRule
from app.schemas.common import UserBrief


class BadgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    icon: str
    rule_type: BadgeRule
    rule_value: int | None = None
    status: ActiveStatus
    created_at: dt.datetime
    holders_count: int = 0


class BadgeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    icon: str = Field(default="🏅", max_length=60)
    rule_type: BadgeRule
    rule_value: int | None = Field(default=None, ge=1)
    status: ActiveStatus = ActiveStatus.active

    @model_validator(mode="after")
    def check_rule(self):
        if self.rule_type == BadgeRule.manual and self.rule_value is not None:
            raise ValueError("Manual badges must not have a rule value")
        if self.rule_type != BadgeRule.manual and self.rule_value is None:
            raise ValueError("Automatic badges require a rule value")
        return self


class BadgeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=60)
    rule_type: BadgeRule | None = None
    rule_value: int | None = Field(default=None, ge=1)
    status: ActiveStatus | None = None


class BadgeAwardIn(BaseModel):
    user_id: int


class UserBadgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    badge: BadgeOut
    awarded_at: dt.datetime
    awarded_by: int | None = None


class BadgeHolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user: UserBrief
    awarded_at: dt.datetime
    awarded_by: int | None = None
