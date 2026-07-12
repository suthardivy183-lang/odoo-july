import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, enum_column
from app.models.enums import ERPType, Scope


class ERPOperation(TimestampMixin, Base):
    __tablename__ = "erp_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    op_type: Mapped[ERPType] = mapped_column(enum_column(ERPType))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    op_date: Mapped[dt.date] = mapped_column(Date, index=True)
    reference_no: Mapped[str] = mapped_column(String(40), unique=True)
    amount_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    distance_km: Mapped[float | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    department = relationship("Department")
    creator = relationship("User")
    lines = relationship(
        "ERPOperationLine", back_populates="operation", cascade="all, delete-orphan"
    )


class ERPOperationLine(Base):
    __tablename__ = "erp_operation_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("erp_operations.id"), index=True)
    resource: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(20))

    operation = relationship("ERPOperation", back_populates="lines")
    carbon_transaction = relationship(
        "CarbonTransaction", back_populates="erp_line", uselist=False
    )


class CarbonTransaction(TimestampMixin, Base):
    __tablename__ = "carbon_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    erp_line_id: Mapped[int | None] = mapped_column(
        ForeignKey("erp_operation_lines.id"), unique=True
    )
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    activity_date: Mapped[dt.date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(20))
    emission_factor_id: Mapped[int] = mapped_column(ForeignKey("emission_factors.id"))
    factor_value_snapshot: Mapped[float] = mapped_column(Numeric(12, 4))
    factor_version_snapshot: Mapped[int] = mapped_column(Integer)
    co2e_kg: Mapped[float] = mapped_column(Numeric(16, 3))
    scope: Mapped[Scope] = mapped_column(enum_column(Scope))
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    erp_line = relationship("ERPOperationLine", back_populates="carbon_transaction")
    department = relationship("Department")
    emission_factor = relationship("EmissionFactor")
    creator = relationship("User")
