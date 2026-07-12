import datetime as dt

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, enum_column
from app.models.enums import CSRStatus, ParticipationStatus


class CSRActivity(TimestampMixin, Base):
    __tablename__ = "csr_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    location: Mapped[str] = mapped_column(String(160))
    organizer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    capacity: Mapped[int] = mapped_column(Integer, default=50)
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date] = mapped_column(Date)
    budget_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    points: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[CSRStatus] = mapped_column(enum_column(CSRStatus), default=CSRStatus.draft)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    category = relationship("Category")
    organizer = relationship("User", foreign_keys=[organizer_user_id])
    participations = relationship(
        "CSRParticipation", back_populates="activity", cascade="all, delete-orphan"
    )


class CSRParticipation(TimestampMixin, Base):
    __tablename__ = "csr_participations"
    __table_args__ = (UniqueConstraint("activity_id", "user_id", name="uq_csr_participation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("csr_activities.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[ParticipationStatus] = mapped_column(
        enum_column(ParticipationStatus), default=ParticipationStatus.joined
    )
    proof_attachment_id: Mapped[int | None] = mapped_column(ForeignKey("attachments.id"))
    points_earned: Mapped[int | None] = mapped_column(Integer)
    completion_date: Mapped[dt.date | None] = mapped_column(Date)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    approver_comment: Mapped[str | None] = mapped_column(Text)

    activity = relationship("CSRActivity", back_populates="participations")
    user = relationship("User", foreign_keys=[user_id])
    proof = relationship("Attachment")
    approver = relationship("User", foreign_keys=[decided_by])
