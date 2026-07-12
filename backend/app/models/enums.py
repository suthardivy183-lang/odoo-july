import enum


class Role(str, enum.Enum):
    employee = "employee"
    dept_head = "dept_head"
    esg_manager = "esg_manager"
    admin = "admin"


class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"


class ActiveStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class CategoryType(str, enum.Enum):
    csr = "csr"
    challenge = "challenge"


class Scope(str, enum.Enum):
    scope1 = "scope1"
    scope2 = "scope2"
    scope3 = "scope3"


class ERPType(str, enum.Enum):
    purchase = "purchase"
    manufacturing = "manufacturing"
    expense = "expense"
    fleet = "fleet"


class GoalStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    missed = "missed"
    archived = "archived"


class PolicyStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class BadgeRule(str, enum.Enum):
    xp_threshold = "xp_threshold"
    challenge_count = "challenge_count"
    csr_count = "csr_count"
    manual = "manual"


class RedemptionStatus(str, enum.Enum):
    placed = "placed"
    fulfilled = "fulfilled"
    cancelled = "cancelled"
    returned = "returned"


class TrainingStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class CSRStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    completed = "completed"
    archived = "archived"


class ChallengeStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    under_review = "under_review"
    completed = "completed"
    archived = "archived"


class Difficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class EvidenceMode(str, enum.Enum):
    inherit = "inherit"
    required = "required"
    not_required = "not_required"


class ParticipationStatus(str, enum.Enum):
    joined = "joined"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    resubmission_requested = "resubmission_requested"


class AuditStatus(str, enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"


class Severity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IssueStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class XPType(str, enum.Enum):
    challenge_award = "challenge_award"
    csr_award = "csr_award"
    redeem_spend = "redeem_spend"
    redeem_refund = "redeem_refund"
    manual_adjust = "manual_adjust"


class EnergyRating(str, enum.Enum):
    a_plus = "A+"
    a = "A"
    b = "B"
    c = "C"
    d = "D"
    e = "E"


class EndOfLife(str, enum.Enum):
    recyclable = "recyclable"
    compostable = "compostable"
    landfill = "landfill"
    hazardous = "hazardous"
    take_back = "take_back"


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    approve = "approve"
    reject = "reject"
    resubmission_request = "resubmission_request"
    redeem = "redeem"
    cancel = "cancel"
    fulfill = "fulfill"
    returned = "returned"
    award_badge = "award_badge"
    award_xp = "award_xp"
    settings_change = "settings_change"
    publish = "publish"
    acknowledge = "acknowledge"
    status_change = "status_change"


class NotificationType(str, enum.Enum):
    compliance_new = "compliance_new"
    compliance_overdue = "compliance_overdue"
    csr_decision = "csr_decision"
    challenge_decision = "challenge_decision"
    policy_published = "policy_published"
    policy_reminder = "policy_reminder"
    badge_unlocked = "badge_unlocked"
