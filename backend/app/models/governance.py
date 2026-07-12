import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, enum_column
from app.models.enums import AuditStatus, IssueStatus, Severity


class Audit(TimestampMixin, Base):
    __tablename__ = "audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    auditor_name: Mapped[str] = mapped_column(String(120))
    auditor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    scope_note: Mapped[str] = mapped_column(String(255), default="")
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    audit_date: Mapped[dt.date] = mapped_column(Date)
    findings: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    status: Mapped[AuditStatus] = mapped_column(
        enum_column(AuditStatus), default=AuditStatus.planned
    )

    auditor_user = relationship("User")
    department = relationship("Department")


class ComplianceIssue(TimestampMixin, Base):
    __tablename__ = "compliance_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[Severity] = mapped_column(enum_column(Severity))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    due_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[IssueStatus] = mapped_column(enum_column(IssueStatus), default=IssueStatus.open)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False)
    overdue_notified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    owner = relationship("User", foreign_keys=[owner_user_id])
    department = relationship("Department")
    creator = relationship("User", foreign_keys=[created_by])
