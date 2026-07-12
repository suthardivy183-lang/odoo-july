"""Import all models so Base.metadata knows every table."""

from app.models.core import (
    Attachment,
    AuditLog,
    Department,
    EmailLog,
    Notification,
    OrgSettings,
    User,
)
from app.models.enums import *  # noqa: F401,F403
from app.models.environment import CarbonTransaction, ERPOperation, ERPOperationLine
from app.models.gamification import Challenge, ChallengeParticipation, XPTransaction
from app.models.governance import Audit, ComplianceIssue
from app.models.masterdata import (
    Badge,
    Category,
    EmissionFactor,
    EnvironmentalGoal,
    ESGPolicy,
    PolicyAcknowledgement,
    Product,
    ProductESGProfile,
    Reward,
    RewardRedemption,
    Training,
    TrainingCompletion,
    UserBadge,
)
from app.models.social import CSRActivity, CSRParticipation
from app.models.carbon_accounting import (
    PricingMethod,
    CarbonPricingRule,
    CarbonCostEntry,
    DepartmentCarbonBudget,
)
