import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, enum_column
from app.models.enums import (
    ActiveStatus,
    AuditAction,
    Gender,
    NotificationType,
    Role,
)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(enum_column(Role), default=Role.employee)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    gender: Mapped[Gender] = mapped_column(enum_column(Gender), default=Gender.other)
    job_title: Mapped[str | None] = mapped_column(String(120))
    date_joined: Mapped[dt.date | None] = mapped_column(Date)
    xp_balance: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department = relationship(
        "Department", foreign_keys=[department_id], back_populates="employees"
    )


class Department(TimestampMixin, Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    head_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", use_alter=True, name="fk_department_head")
    )
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    status: Mapped[ActiveStatus] = mapped_column(
        enum_column(ActiveStatus), default=ActiveStatus.active
    )

    head = relationship("User", foreign_keys=[head_user_id], post_update=True)
    parent = relationship("Department", remote_side=[id], backref="children")
    employees = relationship(
        "User", foreign_keys="User.department_id", back_populates="department"
    )


class OrgSettings(TimestampMixin, Base):
    __tablename__ = "org_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    auto_emission_calc: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_requirement: Mapped[bool] = mapped_column(Boolean, default=True)
    badge_auto_award: Mapped[bool] = mapped_column(Boolean, default=True)
    weight_env: Mapped[int] = mapped_column(Integer, default=40)
    weight_social: Mapped[int] = mapped_column(Integer, default=30)
    weight_gov: Mapped[int] = mapped_column(Integer, default=30)
    notification_prefs: Mapped[dict] = mapped_column(JSON, default=dict)
    email_from_name: Mapped[str] = mapped_column(String(120), default="EcoSphere Notifications")
    email_from_address: Mapped[str] = mapped_column(String(255), default="no-reply@ecosphere.local")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[AuditAction] = mapped_column(enum_column(AuditAction))
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    entity_label: Mapped[str | None] = mapped_column(String(255))
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    actor = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[NotificationType] = mapped_column(enum_column(NotificationType))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user = relationship("User")


class EmailLog(Base):
    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    to_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    notif_type: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    to_user = relationship("User")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500), unique=True)
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    context: Mapped[str] = mapped_column(String(40), default="other")
    entity_type: Mapped[str | None] = mapped_column(String(60), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    uploader = relationship("User")
