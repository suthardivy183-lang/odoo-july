import datetime as dt
from sqlalchemy import Date, DateTime, ForeignKey, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class DepartmentRiskSnapshot(Base):
    __tablename__ = "department_risk_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    snapshot_date: Mapped[dt.date] = mapped_column(Date, index=True)
    environmental_risk: Mapped[float] = mapped_column(Float)
    social_risk: Mapped[float] = mapped_column(Float)
    governance_risk: Mapped[float] = mapped_column(Float)
    overall_risk: Mapped[float] = mapped_column(Float)

    department = relationship("Department")


class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    alert_type: Mapped[str] = mapped_column(String(40))  # e.g., threshold_exceeded, critical_status
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    department = relationship("Department")

