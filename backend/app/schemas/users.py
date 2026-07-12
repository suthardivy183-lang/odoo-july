import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import Gender, Role


class UserCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    role: Role = Role.employee
    department_id: int | None = None
    gender: Gender = Gender.other
    job_title: str | None = Field(default=None, max_length=120)
    date_joined: dt.date | None = None
    is_active: bool = True

    @field_validator("employee_code", "full_name")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("job_title")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class UserUpdate(BaseModel):
    employee_code: str | None = Field(default=None, min_length=1, max_length=20)
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    department_id: int | None = None
    gender: Gender | None = None
    job_title: str | None = Field(default=None, max_length=120)
    date_joined: dt.date | None = None
    is_active: bool | None = None

    @field_validator("employee_code", "full_name")
    @classmethod
    def clean_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("job_title")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class ManagedUserOut(BaseModel):
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
    updated_at: dt.datetime
