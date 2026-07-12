"""Shared Pydantic schemas used across modules."""

import datetime as dt
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from app.models.enums import Gender, Role

T = TypeVar("T")


class Msg(BaseModel):
    detail: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: Role
    department_id: int | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    email: str
    full_name: str
    role: Role
    department_id: int | None = None
    department_name: str | None = None
    gender: Gender
    job_title: str | None = None
    date_joined: dt.date | None = None
    xp_balance: int
    is_active: bool
    created_at: dt.datetime


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    mime: str
    size_bytes: int
    context: str
    created_at: dt.datetime
