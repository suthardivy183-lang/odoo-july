export type Role = "employee" | "dept_head" | "esg_manager" | "admin";
export type ParticipationStatus =
  | "joined" | "submitted" | "approved" | "rejected" | "resubmission_requested";

export interface UserBrief {
  id: number;
  full_name: string;
  email: string;
  role: Role;
  department_id: number | null;
}

export interface UserOut extends UserBrief {
  employee_code: string;
  department_name: string | null;
  gender: string;
  job_title: string | null;
  xp_balance: number;
  is_active: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
}

export interface AttachmentOut {
  id: number;
  original_name: string;
  mime: string;
  size_bytes: number;
  context: string;
  created_at: string;
}

export interface Category {
  id: number;
  name: string;
  type: "csr" | "challenge";
  status: "active" | "inactive";
  created_at: string;
}

export interface BadgeOut {
  id: number;
  name: string;
  description: string;
  icon: string;
  rule_type: "xp_threshold" | "challenge_count" | "csr_count" | "manual";
  rule_value: number | null;
  status: "active" | "inactive";
  holders_count: number;
  created_at: string;
}

export interface UserBadgeOut {
  id: number;
  badge: BadgeOut;
  awarded_at: string;
  awarded_by: number | null;
}

export interface RewardOut {
  id: number;
  name: string;
  description: string;
  points_cost: number;
  stock: number;
  status: "active" | "inactive";
  redeemed_count: number;
  created_at: string;
}

export interface CSRActivityOut {
  id: number;
  title: string;
  description: string;
  category_id: number;
  category_name: string | null;
  location: string;
  organizer: UserBrief | null;
  capacity: number;
  start_date: string;
  end_date: string;
  budget_inr: number | null;
  points: number;
  status: "draft" | "active" | "completed" | "archived";
  joined_count: number;
  my_participation_id: number | null;
  my_participation_status: ParticipationStatus | null;
  created_at: string;
}

export interface CSRParticipationOut {
  id: number;
  activity_id: number;
  activity_title: string | null;
  activity_points: number | null;
  user: UserBrief;
  status: ParticipationStatus;
  proof: AttachmentOut | null;
  points_earned: number | null;
  completion_date: string | null;
  approver: UserBrief | null;
  decided_at: string | null;
  approver_comment: string | null;
  created_at: string;
}

export interface ChallengeOut {
  id: number;
  title: string;
  category_id: number;
  category_name: string | null;
  description: string;
  xp: number;
  difficulty: "easy" | "medium" | "hard";
  evidence: "inherit" | "required" | "not_required";
  deadline: string;
  status: "draft" | "active" | "under_review" | "completed" | "archived";
  participant_count: number;
  my_participation_id: number | null;
  my_participation_status: ParticipationStatus | null;
  my_progress: number | null;
  created_at: string;
}

export interface ChallengeParticipationOut {
  id: number;
  challenge_id: number;
  challenge_title: string | null;
  challenge_xp: number | null;
  challenge_evidence: "inherit" | "required" | "not_required" | null;
  user: UserBrief;
  progress: number;
  status: ParticipationStatus;
  proof: AttachmentOut | null;
  xp_awarded: number | null;
  completion_date: string | null;
  approver: UserBrief | null;
  decided_at: string | null;
  approver_comment: string | null;
  created_at: string;
}

export interface XPSummaryOut {
  xp_balance: number;
  lifetime_earned: number;
  approved_challenges: number;
  approved_csr: number;
  badges_count: number;
}

export interface XPTransactionOut {
  id: number;
  amount: number;
  type: string;
  description: string;
  balance_after: number;
  created_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  user: UserBrief;
  department_name: string | null;
  xp: number;
}

export interface LeaderboardOut {
  period: "weekly" | "monthly" | "all";
  start_date: string | null;
  end_date: string | null;
  entries: LeaderboardEntry[];
  my_rank: number | null;
  my_xp: number;
}

export interface RedemptionOut {
  id: number;
  reward_id: number;
  reward_name: string | null;
  user: UserBrief;
  points_spent: number;
  status: "placed" | "fulfilled" | "cancelled" | "returned";
  created_at: string;
  updated_at: string;
}

export interface NotificationOut {
  id: number;
  type: string;
  title: string;
  body: string;
  entity_type: string | null;
  entity_id: number | null;
  is_read: boolean;
  created_at: string;
}

export interface EmailLogOut {
  id: number;
  to_email: string;
  subject: string;
  body: string;
  notif_type: string;
  created_at: string;
}

export interface EmployeeDashboardOut {
  xp_balance: number;
  lifetime_earned: number;
  my_rank: number | null;
  badges_count: number;
  active_challenge_participations: number;
  approved_challenges: number;
  csr_participations: number;
  approved_csr: number;
  pending_policy_acks: number;
  unread_notifications: number;
  active_challenges_open: number;
  active_csr_open: number;
}

export interface HeadDashboardOut {
  department_ids: number[];
  headcount: number;
  pending_csr_approvals: number;
  pending_challenge_approvals: number;
  csr_participation_rate: number;
  challenge_completion_rate: number;
  gender_distribution: { gender: string; count: number }[];
  engagement_trend: { month: string; csr: number; challenges: number }[];
  top_performers: { user: UserBrief; department_name: string | null; xp_balance: number }[];
  as_of: string;
}

export interface DigitalTwinScenario {
  current_esg_score: number;
  fleet_electrification_pct: number;
  remote_employee_pct: number;
  remote_days_per_week: number;
  supplier_switch_pct: number;
  supplier_emissions_improvement_pct: number;
  supplier_from: string;
  supplier_to: string;
  period: "month" | "quarter" | "fy" | "all";
}

export interface DigitalTwinResult {
  data_source: "live_ledger" | "planning_baseline" | "demo_baseline";
  period_start: string;
  period_end: string;
  current_esg_score: number;
  scenario_esg_score: number;
  score_uplift: number;
  current_carbon_kg: number;
  scenario_carbon_kg: number;
  carbon_reduction_kg: number;
  carbon_reduction_pct: number;
  annual_savings_inr: number;
  annual_savings_lakh: number;
  breakdown: {
    key: "fleet" | "remote" | "supplier";
    label: string;
    baseline_carbon_kg: number;
    reduction_kg: number;
    reduction_pct_of_total: number;
    assumption: string;
  }[];
  projection: {
    year: string;
    current_carbon_kg: number;
    scenario_carbon_kg: number;
  }[];
  methodology: string[];
}
