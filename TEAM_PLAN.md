# EcoSphere — Two-Person Work Split

Repo state audited at commit `09ddad7`. This plan divides ALL remaining work
between **Track A (Divy)** and **Track B (teammate)**. Read
`backend/CONTRACT.md` before writing any backend module — it is the law for
router conventions, business rules, and file ownership.

---

## 0. Where the project stands

### Already done (the FROZEN kernel — nobody edits these)

| Area | Files | Status |
|---|---|---|
| DB models (every entity: users, departments, categories, emission factors, product ESG profiles, goals, ERP ops, carbon txns, CSR, challenges, participations, policies + acknowledgements, trainings, audits, compliance, badges, rewards, XP ledger, redemptions, notifications, email logs, attachments, org settings, audit logs) | `backend/app/models/*` | ✅ |
| Enums for every status/lifecycle | `backend/app/models/enums.py` | ✅ |
| JWT auth API + role guards (`require_admin` / `require_esg` / `require_head`) + bcrypt | `backend/app/api/auth.py`, `core/deps.py`, `core/security.py` | ✅ |
| File upload API + validation service | `backend/app/api/files.py`, `services/files.py` | ✅ |
| Core services: audit log, notify (in-app + mock email), org settings, dept-hierarchy helpers, XP engine (award-once, redeem/cancel/fulfill/return), badge auto-award, compliance overdue check, policy reminders | `backend/app/services/*` | ✅ |
| APScheduler jobs: compliance overdue (5 min), policy reminders (daily 09:00 IST), badge sweep (hourly) | `backend/app/core/scheduler.py` | ✅ |
| App wiring, CORS, health, `create_all` on startup (no Alembic — by design) | `backend/app/main.py` | ✅ |
| Dependency pins incl. reportlab (PDF), openpyxl (Excel), faker (seed) | `backend/requirements.txt` | ✅ |
| Frontend dependency choices (Vite, React 19, router, TanStack Query, RHF+zod, Radix/shadcn, Recharts, sonner) | `frontend/package.json` | ✅ |

### Not done (this plan splits it)

1. **23 backend API modules** — every router except `auth` and `files` is a 4-line stub, each needs `app/api/<module>.py` + `app/schemas/<module>.py`.
2. **The entire frontend** — no `src/`, no Vite config, no index.html. Everything from scaffold to dashboards.
3. **Seed script** — `app/seed/` is empty.
4. **Docs** — README is empty; ER diagram, setup instructions, demo credentials, deployment guide missing.

---

## 1. Ground rules

- **Kernel frozen.** Never edit `models/`, `services/`, `core/`, `db/`, `main.py`, `schemas/common.py`, `utils/`. If a schema change seems unavoidable, stop and discuss (no Alembic — a change means drop DB + reseed for both of us).
- **Backend ownership** = exactly `app/api/<module>.py` + `app/schemas/<module>.py` per CONTRACT.md. Never touch the other track's module files.
- **Frontend ownership by directory** (mirrors backend split):
  - Track B owns the platform: `src/app/` (shell, router, providers), `src/components/ui/`, `src/lib/` (api client, auth), plus its own `src/features/*`.
  - Track A owns only its `src/features/*` directories.
  - **Route + nav registration is append-only:** `src/app/routes-track-a.tsx` and `routes-track-b.tsx` each export a `RouteObject[]`; the shell concatenates them. Same pattern for nav items (`nav-track-a.ts` / `nav-track-b.ts`, grouped per role). Nobody edits the other's registry file.
  - After Milestone 1, `components/ui/` and `lib/` are frozen too — ping before changing.
- **Git:** branches `track-a` / `track-b`, merge to `main` at every milestone (small merges beat one big one), pull `main` daily. Commit format `feat: ...` / `fix: ...`.
- **Note for CONTRACT.md readers:** its paths are Windows-style; on macOS the venv python is `backend/.venv/bin/python`. The self-check is the same: `python -c "import app.api.<module>"` must pass from `backend/`.

---

## 2. Track A — Divy: ESG core (backend-first)

### A-1. Backend modules (15 stubs), in this build order

| # | Module | What it must cover |
|---|---|---|
| 1 | `departments` | CRUD, one head per dept, unlimited parent nesting (use `would_create_cycle`), auto employee counts (`dept_employee_counts`), active/inactive |
| 2 | `users` | Admin user/employee management: list/create/edit/deactivate, role + department + gender fields, password set/reset |
| 3 | `emission_factors` | CRUD with versioning, scope 1/2/3, effective date, status; "active factor" resolution for a source type |
| 4 | `products` | Product + ESG profile (energy rating, recycled %, end-of-life route, certifications) visible on product profile |
| 5 | `goals` | Environmental goal CRUD: baseline, target, deadline, owner dept, progress updates (audited) |
| 6 | `erp` | Simulated ERP ops: purchase / manufacturing / expense / fleet. On create, if org setting `auto_emission_calculation` → create carbon txn via matching active factor |
| 7 | `carbon` | Manual carbon txns (any authorized user), edits **ESG/Admin only** with audit before/after snapshots, calculation breakdown (input × factor vX = result), dept/scope/source summaries + trend endpoints for dashboards |
| 8 | `policies` | Policy CRUD, draft→published→archived, republish bumps version + resets acks, employee acknowledge endpoint, ack-status matrix, manual reminder trigger (calls kernel service) |
| 9 | `trainings` | Training CRUD + employee "complete" endpoint (feeds Social score) |
| 10 | `audits` | Audit CRUD: auditor, scope, date, findings, evidence attachments, 0–100 score |
| 11 | `compliance` | Issue CRUD (owner + due date mandatory), lifecycle per CONTRACT.md, `refresh_overdue_flag` after status/due changes, `compliance_new` notification |
| 12 | `scores` | Scoring engine — formulas in §5. Endpoints: org summary, per-dept score + full breakdown, weights read (write lives in `settings`) |
| 13 | `settings` | Org settings read/update (toggles, weights validated to sum 100, notification channel prefs) — every change audited with before/after |
| 14 | `audit_logs` | Paginated/filterable audit-trail listing (entity, actor, action, date) |
| 15 | `reports` | Environmental / Social / Governance / ESG Summary + **Custom Report Builder** (pick modules + the 6 filters: department, date range, module, employee, challenge, ESG category). Instant PDF (reportlab), Excel (openpyxl), CSV exports |

### A-2. Frontend pages (build after Track B's foundation lands, ~Milestone 1)

Master data: Departments (tree view + head + counts), Employees admin, Emission Factors (version history), Products + ESG profile, Goals (progress bars).
Environmental: ERP operations console, Carbon ledger with breakdown dialog + edit-with-audit, Environmental dashboard (dept/scope/source Recharts, trends, goal progress).
Governance: Policies admin + employee "read & acknowledge" flow, Trainings, Audits, Compliance board with overdue highlighting.
Platform: Score breakdown page (org + per-dept, explain-the-math panel), Reports + Custom Builder (filters → preview table → export buttons), Settings page (links to Track B's email log), Audit-log viewer, **ESG Manager dashboard**, **Admin dashboard**.

### A-3. Docs

ER diagram (generate from models), deployment guide, API-docs pointer (FastAPI `/docs`).

---

## 3. Track B — teammate: frontend platform + engagement

### B-1. Frontend foundation — FIRST PRIORITY, target end of day 1 (it blocks Track A's UI work)

- Vite + React 19 + TS scaffold, Tailwind + shadcn theme: green/white/dark-gray tokens, dark mode toggle, per design direction.
- App shell: sidebar + topbar, role-aware nav from the two nav registries, protected routes.
- Login page against the existing `/api/v1/auth` (already working — test with Swagger).
- API client (fetch wrapper with JWT + error toasts) + TanStack Query setup.
- Shared UI kit: DataTable (pagination matching `Page[T]`), FormDialog (RHF+zod), ConfirmDialog, FileUpload (jpg/png/pdf, 10 MB, wired to `/files`), StatusBadge, EmptyState, PageHeader, loading skeletons, chart wrapper components.

### B-2. Backend modules (8 stubs)

| # | Module | What it must cover |
|---|---|---|
| 1 | `categories` | CSR + Challenge category CRUD |
| 2 | `csr` | Activity CRUD + lifecycle (draft→active→completed, archive anytime), employee join, proof upload link, Dept-Head decisions via `can_decide_for` + org evidence rule + `award_once_for_csr` + badge eval + notify — all per CONTRACT.md |
| 3 | `challenges` | Challenge CRUD (mandatory fields incl. difficulty + evidence mode), lifecycle draft→active→under_review→completed (+archive from any), participation, 0–100% progress (head-editable), proof, decisions with per-challenge evidence override, `award_once_for_challenge` |
| 4 | `gamification` | XP balance + full transaction history, weekly/monthly/all-time leaderboards **with shared-rank ties**, redemption endpoints wrapping kernel `redeem/cancel/fulfill/return` (map `XPError`→400) |
| 5 | `badges` | Badge CRUD (rule, threshold, icon, status), admin manual award, "my badges" |
| 6 | `rewards` | Reward CRUD with stock + status, catalog view |
| 7 | `notifications` | My notifications list/mark-read, **email-log listing** (Track A's settings page links here) |
| 8 | `dashboards` | One-call aggregates for Employee dashboard and Dept Head dashboard (pending approvals count, dept participation, dept score via Track A's `/scores`) |

### B-3. Frontend pages

Employee: dashboard (XP, badges, active challenges/CSR, policies-to-ack pulled from A's endpoint, leaderboard widget), CSR list/detail/join/upload-proof, Challenges list/detail/participate/progress, XP history, Badge gallery, Rewards store + my redemptions (cancel), Leaderboard page, Notification center + mock email log.
Dept Head: dashboard + **approvals inbox** (CSR + challenge queues, approve/reject/resubmit with required comment), department analytics (participation, diversity, engagement charts).
Master data screens for categories/badges/rewards.

### B-4. Seed script (`backend/app/seed/`) — depends only on frozen models/services, so start anytime

Faker-driven, idempotent (wipe + recreate), quantities from the spec: **50 employees** (gender + dept spread for diversity stats) across **10 departments** (nested, each with a head), **5 policies** (mix of published w/ deadlines + one republished to show re-ack), **10 challenges** (all statuses + evidence modes), **20 CSR activities**, **20 compliance issues** (several past-due-and-open so the overdue sweep + notifications fire on startup), **10 rewards** (one at zero stock), **15 badges** (all three auto rules + manual), active emission factors **incl. diesel 2.68 kgCO₂/L**, ERP ops incl. the demo case (Manufacturing buys 100 L diesel → auto txn 268 kg), participations in every approval state with proofs, XP history, redemptions (placed/fulfilled/cancelled/returned), policy acks, training completions, and **4 documented demo accounts** (employee / dept head / ESG manager / admin) in the README.

### B-5. Docs

README quickstart (Windows + macOS), demo credentials table, judge demo script.

---

## 4. Cross-track contracts (the ONLY places we depend on each other)

1. **B → A:** frontend foundation (shell, nav registries, UI kit, api client) by end of day 1. If it slips past day 2, A takes over the foundation and hands B the `products` + `goals` + `trainings` modules in exchange.
2. **A → B:** `/scores/departments/{id}` (dept ESG score for the Head dashboard) by Milestone 2.
3. **A ↔ B:** A's settings page links to B's email-log route (`/notifications/email-logs`).
4. **Seed order** inside B's script: core org data (users, depts, factors) → engagement data → run overdue/badge sweeps once.
5. Everything else goes through the **frozen kernel** — no other coupling allowed.

---

## 5. Scoring formula spec (Track A implements; recorded here so it's not tribal knowledge)

All components 0–100; a component with no data is **excluded** from its pillar mean (never counted as zero); a pillar with no components shows "—" and the total re-normalizes over available pillar weights. Every endpoint returns the numbers behind each component so the UI can show the math.

- **Environmental** = mean of:
  - *Goal completion:* average progress % of the dept's active+completed goals (capped at 100).
  - *Emission performance:* min-max normalization of per-employee emissions across departments for the period — lowest emitter 100, highest 0 (single dept ⇒ 100).
- **Social** = mean of:
  - *CSR participation rate:* distinct employees with ≥1 approved CSR participation ÷ active employees × 100.
  - *Diversity balance:* 100 × (1 − |male share − female share|) over active employees.
  - *Training completion:* completions ÷ (active trainings × active employees) × 100.
- **Governance** = mean of:
  - *Policy acknowledgement rate:* completed acks ÷ required acks (current versions) × 100.
  - *Audit score:* average of completed-audit scores (already 0–100).
  - *Compliance health:* resolved+closed ÷ total issues × 100 (no issues ⇒ 100), minus 5 per currently-overdue open issue, floored at 0.
- **Dept total** = Σ pillar × org weight (weights validated to sum 100; default 40/30/30).
- **Org score** = employee-count-weighted mean of dept totals.
- Period filters use kernel `resolve_period` (month / quarter / FY Apr–Mar / all).

---

## 6. Milestones

| Milestone | Track A | Track B | Joint check |
|---|---|---|---|
| **M0** (day 1) | Modules 1–5 (departments, users, factors, products, goals) | Foundation + login working end-to-end | Both can run backend + frontend locally |
| **M1** | Modules 6–9 (erp, carbon, policies, trainings) | Backend modules 1–4 (categories, csr, challenges, gamification) + seed v1 | Diesel demo auto-calc verified; CSR approval loop works in Swagger |
| **M2** | Modules 10–14 (audits, compliance, scores, settings, audit_logs) + start A pages | Modules 5–8 + employee-facing pages | Head dashboard shows A's dept score; evidence toggle respected in both flows |
| **M3** | Reports module + remaining A pages + both admin dashboards | Approvals inbox, leaderboard, rewards store, notification center, seed v2 (full quantities) | Scores/reports light up from seeded data |
| **M4** (last day) | ER diagram, deployment guide, bugfix | README, demo script, bugfix | **Cross-test: each person demos the OTHER track's workflows**, then full judge rehearsal |

---

## 7. Definition of done (every module, both tracks)

Server-side permission enforcement (per CONTRACT.md guards) · backend + frontend validation · `log_action` on every mutation · notifications where specified · loading/empty/error states · confirmation on destructive actions · seeded demo data · reachable from the role-aware nav (nothing API-only).
