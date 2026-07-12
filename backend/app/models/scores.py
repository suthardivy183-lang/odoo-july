import datetime as dt

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class DepartmentScoreSnapshot(Base):
    """A point-in-time ESG score for one department over one period.

    Pillar columns are nullable: NULL means the pillar had no scoreable data
    for the period (excluded from the total, never counted as zero) per the
    scoring spec. ``components_json`` stores the raw inputs behind every
    component so the UI can "explain the math".
    """

    __tablename__ = "department_score_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "department_id",
            "snapshot_date",
            "period_type",
            name="uq_dept_score_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), index=True
    )
    snapshot_date: Mapped[dt.date] = mapped_column(Date, index=True)
    period_type: Mapped[str] = mapped_column(String(10))  # month|quarter|fy|all
    environmental_score: Mapped[float | None] = mapped_column(Float)
    social_score: Mapped[float | None] = mapped_column(Float)
    governance_score: Mapped[float | None] = mapped_column(Float)
    total_score: Mapped[float] = mapped_column(Float)
    components_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    department = relationship("Department")


class OrgScoreSnapshot(Base):
    """Employee-count-weighted organization ESG score over one period."""

    __tablename__ = "org_score_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_date", "period_type", name="uq_org_score_snapshot"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_date: Mapped[dt.date] = mapped_column(Date, index=True)
    period_type: Mapped[str] = mapped_column(String(10))  # month|quarter|fy|all
    environmental_score: Mapped[float | None] = mapped_column(Float)
    social_score: Mapped[float | None] = mapped_column(Float)
    governance_score: Mapped[float | None] = mapped_column(Float)
    total_score: Mapped[float] = mapped_column(Float)
    dept_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
