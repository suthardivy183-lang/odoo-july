import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, enum_column
from app.models.enums import (
    ActiveStatus,
    BadgeRule,
    CategoryType,
    EndOfLife,
    EnergyRating,
    ERPType,
    GoalStatus,
    PolicyStatus,
    RedemptionStatus,
    Scope,
    TrainingStatus,
)


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "type", name="uq_category_name_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    type: Mapped[CategoryType] = mapped_column(enum_column(CategoryType))
    status: Mapped[ActiveStatus] = mapped_column(
        enum_column(ActiveStatus), default=ActiveStatus.active
    )


class EmissionFactor(TimestampMixin, Base):
    __tablename__ = "emission_factors"
    __table_args__ = (
        UniqueConstraint("name", "source_type", "version", name="uq_factor_name_source_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[ERPType] = mapped_column(enum_column(ERPType))
    unit: Mapped[str] = mapped_column(String(20))
    factor_value: Mapped[float] = mapped_column(Numeric(12, 4))
    scope: Mapped[Scope] = mapped_column(enum_column(Scope))
    effective_date: Mapped[dt.date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ActiveStatus] = mapped_column(
        enum_column(ActiveStatus), default=ActiveStatus.active
    )


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    category: Mapped[str | None] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(20), default="unit")
    unit_price_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ActiveStatus] = mapped_column(
        enum_column(ActiveStatus), default=ActiveStatus.active
    )

    esg_profile = relationship(
        "ProductESGProfile", back_populates="product", uselist=False, cascade="all, delete-orphan"
    )


class ProductESGProfile(TimestampMixin, Base):
    __tablename__ = "product_esg_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), unique=True)
    carbon_footprint_kgco2e_per_unit: Mapped[float | None] = mapped_column(Numeric(14, 3))
    recycled_content_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    recyclable_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    energy_rating: Mapped[EnergyRating | None] = mapped_column(enum_column(EnergyRating))
    water_usage_l_per_unit: Mapped[float | None] = mapped_column(Numeric(14, 3))
    hazardous_substances: Mapped[bool] = mapped_column(Boolean, default=False)
    hazard_notes: Mapped[str | None] = mapped_column(Text)
    certifications: Mapped[list | None] = mapped_column(JSON)
    end_of_life: Mapped[EndOfLife | None] = mapped_column(enum_column(EndOfLife))
    supplier_esg_score: Mapped[int | None] = mapped_column(Integer)
    sustainability_notes: Mapped[str | None] = mapped_column(Text)
    last_assessed_on: Mapped[dt.date | None] = mapped_column(Date)

    product = relationship("Product", back_populates="esg_profile")


class EnvironmentalGoal(TimestampMixin, Base):
    __tablename__ = "environmental_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    metric_unit: Mapped[str] = mapped_column(String(30))
    baseline_value: Mapped[float] = mapped_column(Numeric(14, 3))
    target_value: Mapped[float] = mapped_column(Numeric(14, 3))
    current_value: Mapped[float] = mapped_column(Numeric(14, 3))
    deadline: Mapped[dt.date] = mapped_column(Date)
    owner_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    linked_factor_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[GoalStatus] = mapped_column(enum_column(GoalStatus), default=GoalStatus.active)

    owner_department = relationship("Department")


class ESGPolicy(TimestampMixin, Base):
    __tablename__ = "esg_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[PolicyStatus] = mapped_column(
        enum_column(PolicyStatus), default=PolicyStatus.draft
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    ack_deadline_days: Mapped[int] = mapped_column(Integer, default=14)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    creator = relationship("User")
    acknowledgements = relationship(
        "PolicyAcknowledgement", back_populates="policy", cascade="all, delete-orphan"
    )


class PolicyAcknowledgement(Base):
    __tablename__ = "policy_acknowledgements"
    __table_args__ = (
        UniqueConstraint("policy_id", "policy_version", "user_id", name="uq_policy_ack"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("esg_policies.id"), index=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    acknowledged_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    policy = relationship("ESGPolicy", back_populates="acknowledgements")
    user = relationship("User")


class Badge(TimestampMixin, Base):
    __tablename__ = "badges"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(60), default="🏅")
    rule_type: Mapped[BadgeRule] = mapped_column(enum_column(BadgeRule))
    rule_value: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[ActiveStatus] = mapped_column(
        enum_column(ActiveStatus), default=ActiveStatus.active
    )


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    badge_id: Mapped[int] = mapped_column(ForeignKey("badges.id"), index=True)
    awarded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    awarded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    user = relationship("User", foreign_keys=[user_id])
    badge = relationship("Badge")
    awarder = relationship("User", foreign_keys=[awarded_by])


class Reward(TimestampMixin, Base):
    __tablename__ = "rewards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    points_cost: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ActiveStatus] = mapped_column(
        enum_column(ActiveStatus), default=ActiveStatus.active
    )


class RewardRedemption(TimestampMixin, Base):
    __tablename__ = "reward_redemptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reward_id: Mapped[int] = mapped_column(ForeignKey("rewards.id"), index=True)
    points_spent: Mapped[int] = mapped_column(Integer)
    status: Mapped[RedemptionStatus] = mapped_column(
        enum_column(RedemptionStatus), default=RedemptionStatus.placed
    )

    user = relationship("User")
    reward = relationship("Reward")


class Training(TimestampMixin, Base):
    __tablename__ = "trainings"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[TrainingStatus] = mapped_column(
        enum_column(TrainingStatus), default=TrainingStatus.active
    )


class TrainingCompletion(Base):
    __tablename__ = "training_completions"
    __table_args__ = (UniqueConstraint("training_id", "user_id", name="uq_training_completion"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    training_id: Mapped[int] = mapped_column(ForeignKey("trainings.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    completed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    training = relationship("Training")
    user = relationship("User")
