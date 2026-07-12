# EcoSphere backend — module implementation contract

Read this fully before writing any module. The kernel (models, core services,
auth, files, scheduler) is FROZEN — never modify files outside the ones your
task assigns to you.

## Layout & environment

- Backend root: `C:\Users\Shivam\Desktop\odoo_july\backend`
- Python: `backend\.venv\Scripts\python.exe` (run from `backend/` so `app` imports)
- Self-check your work: `cd backend` then `.venv\Scripts\python.exe -c "import app.api.<your_module>"` must succeed.
- DB: PostgreSQL `ecosphere` (connection via `.env`, already configured). Importing modules does NOT connect.

## Frozen kernel — read these, use them, never edit them

- `app/models/*.py` — all SQLAlchemy models + `app/models/enums.py` (str enums, stored by value)
- `app/db/session.py` — `get_db`, `SessionLocal`, `Base`
- `app/core/deps.py` — `get_current_user`, `require_roles(*roles)`, shortcuts:
  `require_admin` (admin only), `require_esg` (esg_manager|admin),
  `require_head` (dept_head|esg_manager|admin). **Admin passes every guard implicitly.**
- `app/core/security.py` — `hash_password`, `verify_password`
- `app/schemas/common.py` — `Msg`, `Page[T]`, `UserBrief`, `UserOut`, `AttachmentOut`
- `app/utils/time.py` — `IST`, `today_ist`, `now_utc`, `resolve_period(period, date_from, date_to) -> (start_date, end_date)` (period: month|quarter|fy|all, default fy), `date_to_utc_range`, `week_bounds`, `month_bounds`, `fiscal_year_bounds`
- Services (`app/services/`):
  - `audit.py` — `snapshot(obj, fields) -> dict`, `log_action(db, actor_user_id, AuditAction, entity_type, entity_id, entity_label=None, before=None, after=None)`
  - `notify.py` — `notify(db, users_or_user, NotificationType, title, body="", entity_type=None, entity_id=None)` (honors org channel prefs, writes in-app rows + mock email_logs)
  - `org_settings.py` — `get_org_settings(db) -> OrgSettings`
  - `org.py` — `descendant_dept_ids(db, id)`, `managed_dept_ids(db, user)`, `responsible_head(db, dept_id)`, `can_decide_for(db, actor, employee)`, `would_create_cycle(db, dept_id, new_parent_id)`, `dept_employee_counts(db) -> {id: {direct, total}}`
  - `xp.py` — `apply_xp(...)`, `award_once_for_challenge(db, participation_id, actor_id) -> bool`, `award_once_for_csr(db, participation_id, actor_id) -> bool`, `redeem_reward(db, user, reward_id)`, `cancel_redemption`, `fulfill_redemption`, `return_redemption`, `lifetime_earned_xp`, `approved_challenge_count`, `approved_csr_count`; raises `XPError` (map to HTTP 400)
  - `badges.py` — `evaluate_user_badges(db, user)`, `assign_badge_manual(db, user, badge, actor_id)`, `sweep_all(db)`
  - `compliance_rules.py` — `run_overdue_check(db) -> int`, `refresh_overdue_flag(issue)`
  - `policy_reminders.py` — `send_policy_reminders(db, force=False) -> int`, `ack_deadline(policy)`, `pending_user_ids(db, policy)`
  - `files.py` — `save_upload(db, upload_file, user, context, entity_type=None, entity_id=None)`; raises `FileValidationError` (map to HTTP 400)

## Router conventions

- One file per module in `app/api/<module>.py`, overwriting the stub. Export
  `router = APIRouter(tags=["<Tag>"])` (keep the stub's tag). Write FULL paths
  on each route (e.g. `@router.get("/csr/activities")`); `main.py` adds `/api/v1`.
- Pydantic v2 schemas: put them in `app/schemas/<module>.py` and import from the
  router. `model_config = ConfigDict(from_attributes=True)` on outputs. Names:
  `XOut`, `XCreate`, `XUpdate` (Update = all-optional fields).
- Lists: pagination `page: int = 1`, `size: int = Query(20, le=100)` + module
  filters; respond `Page[XOut](items=..., total=...)`. Order newest-first unless
  the spec says otherwise.
- **Transactions: services flush, routers commit.** Call `db.commit()` exactly
  once per mutating request (after all service calls), then `db.refresh(obj)`
  if you return it.
- Errors: `raise HTTPException(status_code, detail="human readable message")`.
  400 = business rule, 403 = permission, 404 = missing, 409 = conflict/duplicate.
- Validate FKs exist before use (404/400 with clear detail).
- Datetime out = ISO; date params = `datetime.date`. Period filters use
  `resolve_period`.

## Cross-cutting business rules

- **Audit everything mutating**: create/update/delete/decisions/transitions →
  `log_action` with `before=snapshot(...)`/`after=snapshot(...)` around edits.
  The kernel already audits XP awards, redemptions and badge grants — do not
  double-log those.
- **Status lifecycles** (reject invalid transitions with 400):
  - Challenge: draft→active→under_review→completed; archived allowed from ANY
    status; no other jumps. (under_review is set manually by ESG or
    automatically when any participant submits proof — see challenges module.)
  - CSR activity: draft→active→completed; archived from any status.
  - Compliance: open→in_progress→resolved→closed, in_progress→open,
    resolved→closed, resolved→in_progress (reopen); set `resolved_at` when
    entering resolved; call `refresh_overdue_flag(issue)` after ANY status or
    due_date change.
  - Policy: draft→published (sets `published_at=now_utc()`); published→archived;
    editing body/title of a PUBLISHED policy requires "republish" flow: version += 1,
    `published_at` reset — acknowledgements of older versions stay but the
    current version starts un-acknowledged.
- **Evidence rules**: CSR approval requires a proof attachment when
  `get_org_settings(db).evidence_requirement` is True. Challenge approval:
  challenge.evidence == required → proof mandatory; not_required → never
  mandatory; inherit → follow org evidence_requirement.
- **Approval scope**: decisions (approve/reject/request resubmission) allowed iff
  `can_decide_for(db, actor, employee)` (admins always; heads for their managed
  departments; never self). ESG managers do NOT decide participations.
- **Participation decisions**: payload `{decision: "approve"|"reject"|"resubmit",
  comment: str}`; comment REQUIRED for reject/resubmit. Sets status
  (approved/rejected/resubmission_requested), `decided_by`, `decided_at`,
  `approver_comment`. On approve call `award_once_for_csr` /
  `award_once_for_challenge` then `evaluate_user_badges(db, employee)`. Send
  `notify(db, employee, NotificationType.csr_decision|challenge_decision, ...)`
  for every decision, then `log_action` with AuditAction.approve/reject/
  resubmission_request.
- **Dept-head data scope**: heads see analytics/lists for
  `managed_dept_ids(db, user)`; ESG/Admin see all. Employees see only their own
  records (routes under `/me/...`).
- Roles are cumulative for self-service: ANY authenticated user can join CSR
  activities/challenges, acknowledge policies, redeem rewards, complete
  trainings, view leaderboard/badges.

## Notifications (use exactly these types)

- `compliance_new` — on compliance issue creation → owner + responsible head + ESG managers
- `compliance_overdue` — kernel handles (scheduler)
- `csr_decision` / `challenge_decision` — on every decision → the employee
- `policy_published` — on publish/republish → all active users
- `policy_reminder` — kernel handles (+ manual send endpoint calls the kernel service)
- `badge_unlocked` — kernel handles

## Module ownership

Each module owns exactly: `app/api/<module>.py` + `app/schemas/<module>.py`
(+ extra service files ONLY if the task assignment lists them). Never touch
another module's files, `main.py`, models, or kernel services.
