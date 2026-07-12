import datetime as dt

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, enum_column
from app.models.enums import (
    ChallengeStatus,
    Difficulty,
    EvidenceMode,
    ParticipationStatus,
    XPType,
)


class Challenge(TimestampMixin, Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    description: Mapped[str] = mapped_column(Text, default="")
    xp: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[Difficulty] = mapped_column(enum_column(Difficulty))
    evidence: Mapped[EvidenceMode] = mapped_column(
        enum_column(EvidenceMode), default=EvidenceMode.inherit
    )
    deadline: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[ChallengeStatus] = mapped_column(
        enum_column(ChallengeStatus), default=ChallengeStatus.draft
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    category = relationship("Category")
    participations = relationship(
        "ChallengeParticipation", back_populates="challenge", cascade="all, delete-orphan"
    )


class ChallengeParticipation(TimestampMixin, Base):
    __tablename__ = "challenge_participations"
    __table_args__ = (
        UniqueConstraint("challenge_id", "user_id", name="uq_challenge_participation"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ParticipationStatus] = mapped_column(
        enum_column(ParticipationStatus), default=ParticipationStatus.joined
    )
    proof_attachment_id: Mapped[int | None] = mapped_column(ForeignKey("attachments.id"))
    xp_awarded: Mapped[int | None] = mapped_column(Integer)
    completion_date: Mapped[dt.date | None] = mapped_column(Date)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    approver_comment: Mapped[str | None] = mapped_column(Text)

    challenge = relationship("Challenge", back_populates="participations")
    user = relationship("User", foreign_keys=[user_id])
    proof = relationship("Attachment")
    approver = relationship("User", foreign_keys=[decided_by])


class XPTransaction(Base):
    __tablename__ = "xp_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)  # positive = earn, negative = spend
    type: Mapped[XPType] = mapped_column(enum_column(XPType))
    ref_type: Mapped[str | None] = mapped_column(String(40))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(255), default="")
    balance_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user = relationship("User")
