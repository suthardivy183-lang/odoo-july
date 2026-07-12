"""EcoSphere demo seed. Run with:  python -m app.seed

Wipes the schema, then loads a deterministic, judge-ready dataset:
54 users / 10 departments / factors + ERP ops with auto carbon transactions /
5 policies (+acks) / 3 trainings / 15 badges / 10 rewards / 20 CSR activities /
10 challenges / participations in every approval state / XP + redemptions /
20 compliance issues (5 overdue) / 5 audits / notifications + email logs.
"""

import datetime as dt
import random
import uuid

from faker import Faker
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models.core import Attachment, Department, User
from app.models.enums import (
    ActiveStatus,
    AuditStatus,
    CategoryType,
    ChallengeStatus,
    CSRStatus,
    Difficulty,
    ERPType,
    EvidenceMode,
    Gender,
    IssueStatus,
    NotificationType,
    ParticipationStatus,
    PolicyStatus,
    Role,
    Scope,
    Severity,
)
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
    Training,
    TrainingCompletion,
)
from app.models.social import CSRActivity, CSRParticipation
from app.seed import data
from app.services.badges import assign_badge_manual, sweep_all
from app.services.compliance_rules import run_overdue_check
from app.services.notify import notify
from app.services.org import responsible_head
from app.services.org_settings import get_org_settings
from app.services.xp import (
    award_once_for_challenge,
    award_once_for_csr,
    cancel_redemption,
    fulfill_redemption,
    redeem_reward,
    return_redemption,
)
from app.utils.time import IST, now_utc, today_ist

rng = random.Random(42)
fake = Faker("en_IN")
Faker.seed(42)

TODAY = today_ist()


def _dtime(d: dt.date, hour: int = 10) -> dt.datetime:
    return dt.datetime.combine(d, dt.time(hour), tzinfo=IST).astimezone(dt.timezone.utc)


def _proof(db: Session, user: User, entity_type: str) -> Attachment:
    rel_dir = "seed"
    target = settings.upload_path / rel_dir
    target.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.png"
    (target / name).write_bytes(data.PROOF_PNG)
    att = Attachment(
        original_name="proof.png",
        stored_path=f"{rel_dir}/{name}",
        mime="image/png",
        size_bytes=len(data.PROOF_PNG),
        uploaded_by=user.id,
        context="proof",
        entity_type=entity_type,
    )
    db.add(att)
    db.flush()
    return att


def seed_users_departments(db: Session) -> tuple[dict[str, Department], dict[str, User], list[User]]:
    pw = hash_password(data.DEMO_PASSWORD)  # one hash reused: seeding 54 users stays fast
    depts: dict[str, Department] = {}
    for name, parent in data.DEPARTMENTS:
        depts[name] = Department(name=name, parent=depts.get(parent))
        db.add(depts[name])
    db.flush()

    counter = iter(range(1, 200))

    def make_user(full_name, email, role, dept, gender, title) -> User:
        user = User(
            employee_code=f"EMP{next(counter):03d}",
            email=email,
            password_hash=pw,
            full_name=full_name,
            role=role,
            department_id=depts[dept].id,
            gender=gender,
            job_title=title,
            date_joined=fake.date_between(dt.date(2018, 1, 1), dt.date(2025, 12, 1)),
        )
        db.add(user)
        return user

    demo = {
        "admin": make_user("Divy Suthar", "admin@ecosphere.in", Role.admin,
                           "Corporate", Gender.male, "Platform Administrator"),
        "esg": make_user("Meera Krishnan", "esg@ecosphere.in", Role.esg_manager,
                         "Sustainability & ESG", Gender.female, "ESG Manager"),
        "head": make_user("Rajesh Verma", "head@ecosphere.in", Role.dept_head,
                          "Manufacturing", Gender.male, "Plant Head"),
        "employee": make_user("Priya Sharma", "employee@ecosphere.in", Role.employee,
                              "Manufacturing", Gender.female, "Process Engineer"),
    }
    make_user("Arjun Nair", "arjun.nair@ecosphere.in", Role.esg_manager,
              "Sustainability & ESG", Gender.male, "Deputy ESG Manager")

    heads: dict[str, User] = {"Manufacturing": demo["head"]}
    used_emails = {u.email for u in db.new if isinstance(u, User)}
    genders = [Gender.male, Gender.female, Gender.other]
    weights = [0.5, 0.45, 0.05]

    def unique_email(name: str) -> str:
        base = name.lower().replace(" ", ".").replace("'", "")
        email, n = f"{base}@ecosphere.in", 1
        while email in used_emails:
            n += 1
            email = f"{base}{n}@ecosphere.in"
        used_emails.add(email)
        return email

    for name, _ in data.DEPARTMENTS:
        if name == "Manufacturing":
            continue
        gender = rng.choices(genders, weights)[0]
        full = fake.name_male() if gender == Gender.male else fake.name_female()
        heads[name] = make_user(full, unique_email(full), Role.dept_head, name, gender,
                                f"Head of {name}")

    employees: list[User] = [demo["employee"]]
    titles = ["Analyst", "Engineer", "Executive", "Coordinator", "Specialist", "Associate"]
    dept_names = [n for n, _ in data.DEPARTMENTS]
    for _ in range(40):
        gender = rng.choices(genders, weights)[0]
        full = fake.name_male() if gender == Gender.male else fake.name_female()
        dept = rng.choice(dept_names)
        employees.append(
            make_user(full, unique_email(full), Role.employee, dept, gender, rng.choice(titles))
        )
    db.flush()
    for name, head in heads.items():
        depts[name].head_user_id = head.id
    db.flush()
    return depts, demo, employees


def seed_master(db: Session, depts, demo) -> dict:
    out: dict = {"csr_cats": {}, "ch_cats": {}, "factors": {}, "badges": {}, "rewards": {}}
    for name in data.CSR_CATEGORIES:
        out["csr_cats"][name] = Category(name=name, type=CategoryType.csr)
        db.add(out["csr_cats"][name])
    for name in data.CHALLENGE_CATEGORIES:
        out["ch_cats"][name] = Category(name=name, type=CategoryType.challenge)
        db.add(out["ch_cats"][name])
    for name, src, unit, value, scope, version, status in data.EMISSION_FACTORS:
        f = EmissionFactor(
            name=name, source_type=ERPType(src), unit=unit, factor_value=value,
            scope=Scope(scope), effective_date=dt.date(2026, 4, 1) if version > 1 else dt.date(2025, 4, 1),
            version=version, status=ActiveStatus(status),
        )
        out["factors"][(name, version)] = f
        db.add(f)
    for name, rule, value, icon, desc in data.BADGES:
        b = Badge(name=name, rule_type=rule, rule_value=value, icon=icon, description=desc)
        out["badges"][name] = b
        db.add(b)
    for name, cost, stock, desc in data.REWARDS:
        r = Reward(name=name, points_cost=cost, stock=stock, description=desc)
        out["rewards"][name] = r
        db.add(r)
    for name, unit, baseline, target, current, dept, factor in data.GOALS:
        db.add(EnvironmentalGoal(
            name=name, metric_unit=unit, baseline_value=baseline, target_value=target,
            current_value=current, deadline=dt.date(2027, 3, 31),
            owner_department_id=depts[dept].id, linked_factor_name=factor,
            description=f"Owned by {dept}; tracked against {factor or 'manual readings'}.",
        ))
    for name, sku, cat, unit, price, rating, recycled, eol in data.PRODUCTS:
        p = Product(name=name, sku=sku, category=cat, unit=unit, unit_price_inr=price,
                    description=f"{name} — part of the sustainable catalogue.")
        db.add(p)
        db.flush()
        db.add(ProductESGProfile(
            product_id=p.id,
            carbon_footprint_kgco2e_per_unit=round(rng.uniform(0.4, 18.0), 2),
            recycled_content_pct=recycled,
            recyclable_pct=min(100, recycled + rng.randint(0, 30)),
            energy_rating=rating,
            water_usage_l_per_unit=round(rng.uniform(1, 40), 1),
            hazardous_substances=(eol == "hazardous"),
            certifications=["ISO 14001"] + (["Energy Star"] if rating else []),
            end_of_life=eol,
            supplier_esg_score=rng.randint(55, 95),
            last_assessed_on=dt.date(2026, 5, 20),
        ))
    db.flush()
    return out


def seed_erp_carbon(db: Session, depts, demo, factors) -> int:
    """ERP operations with auto-created carbon transactions (Auto Emission Calc demo)."""
    f = {name_v: obj for name_v, obj in factors.items()}
    combos = [
        # (dept, factor key, op_type, resource, qty range, unit, inr/unit)
        ("Manufacturing", ("Diesel (Purchase)", 1), ERPType.purchase, "Diesel", (80, 160), "L", 92),
        ("Manufacturing", ("Furnace Oil (Manufacturing)", 1), ERPType.manufacturing, "Furnace oil", (200, 420), "L", 68),
        ("Manufacturing", ("Process Energy (Manufacturing)", 1), ERPType.manufacturing, "Process energy", (5000, 9000), "kWh", 9),
        ("Operations", ("Grid Electricity (Expense)", 2), ERPType.expense, "Electricity bill", (12000, 20000), "kWh", 8),
        ("Corporate", ("Grid Electricity (Expense)", 2), ERPType.expense, "Electricity bill", (3500, 6000), "kWh", 8),
        ("Logistics", ("Diesel Fleet", 1), ERPType.fleet, "Fleet diesel", (400, 700), "L", 92),
        ("Logistics", ("Road Freight (Fleet)", 1), ERPType.fleet, "Road freight", (3000, 6000), "km", 14),
        ("Sales & Marketing", ("Petrol (Purchase)", 1), ERPType.purchase, "Petrol", (60, 140), "L", 104),
    ]
    months = [(2025, 12), (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6), (2026, 7)]
    count = 0
    ref = iter(range(1000, 9999))

    def add_op(dept_name, factor_key, op_type, resource, qty, unit, rate, op_date, reference=None):
        nonlocal count
        factor = f[factor_key]
        op = ERPOperation(
            op_type=op_type, department_id=depts[dept_name].id, op_date=op_date,
            reference_no=reference or f"{op_type.value[:2].upper()}-{next(ref)}",
            amount_inr=round(qty * rate, 2),
            distance_km=qty if unit == "km" else None,
            created_by=demo["admin"].id,
            notes=f"Simulated ERP {op_type.value} operation",
        )
        db.add(op)
        db.flush()
        line = ERPOperationLine(operation_id=op.id, resource=resource, quantity=qty, unit=unit)
        db.add(line)
        db.flush()
        db.add(CarbonTransaction(
            erp_line_id=line.id, department_id=op.department_id, activity_date=op_date,
            description=f"{resource} — {op.reference_no}",
            quantity=qty, unit=unit,
            emission_factor_id=factor.id,
            factor_value_snapshot=factor.factor_value,
            factor_version_snapshot=factor.version,
            co2e_kg=round(qty * float(factor.factor_value), 3),
            scope=factor.scope, is_auto=True, created_by=demo["admin"].id,
        ))
        count += 1

    for year, month in months:
        for dept_name, factor_key, op_type, resource, (lo, hi), unit, rate in combos:
            day = rng.randint(2, 26)
            if (year, month) == (2026, 7):
                day = rng.randint(2, 10)
            qty = rng.randint(lo, hi)
            add_op(dept_name, factor_key, op_type, resource, qty, unit, rate, dt.date(year, month, day))

    # The spec's flagship example: 100 L diesel -> 2.68 -> 268 kg CO2 (auto).
    add_op("Manufacturing", ("Diesel (Purchase)", 1), ERPType.purchase, "Diesel",
           100, "L", 92, dt.date(2026, 7, 6), reference="PO-DEMO-100L")
    db.flush()
    return count


def seed_policies_trainings(db: Session, demo, all_users) -> None:
    published_dates = {0: dt.date(2026, 6, 15), 1: dt.date(2026, 7, 1),
                       2: dt.date(2026, 6, 25), 3: dt.date(2026, 7, 8)}
    policies = []
    for i, (title, deadline_days, status, version) in enumerate(data.POLICIES):
        p = ESGPolicy(
            title=title,
            body=f"# {title}\n\n" + "\n\n".join(fake.paragraphs(4)),
            status=PolicyStatus(status), version=version,
            ack_deadline_days=deadline_days,
            published_at=_dtime(published_dates[i]) if status == "published" else None,
            created_by=demo["esg"].id,
        )
        policies.append(p)
        db.add(p)
    db.flush()

    for p in policies:
        if p.status != PolicyStatus.published:
            continue
        if p.version > 1:  # republished: everyone acked v1, only 40% re-acked v2
            for u in all_users:
                db.add(PolicyAcknowledgement(
                    policy_id=p.id, policy_version=1, user_id=u.id,
                    acknowledged_at=_dtime(dt.date(2026, 5, rng.randint(12, 28))),
                ))
            ackers = rng.sample(all_users, int(len(all_users) * 0.4))
        else:
            ackers = rng.sample(all_users, int(len(all_users) * 0.75))
        for u in ackers:
            base = p.published_at.date()
            db.add(PolicyAcknowledgement(
                policy_id=p.id, policy_version=p.version, user_id=u.id,
                acknowledged_at=_dtime(base + dt.timedelta(days=rng.randint(0, 6))),
            ))
    for name, desc in data.TRAININGS:
        t = Training(name=name, description=desc, due_date=dt.date(2026, 8, 31))
        db.add(t)
        db.flush()
        for u in rng.sample(all_users, int(len(all_users) * 0.6)):
            db.add(TrainingCompletion(
                training_id=t.id, user_id=u.id,
                completed_at=_dtime(dt.date(2026, rng.randint(5, 7), rng.randint(1, 11))),
            ))
    db.flush()


def _decide(db, part, decision, decider, comment, award_fn, notif_type, label, do_notify):
    part.status = {
        "approve": ParticipationStatus.approved,
        "reject": ParticipationStatus.rejected,
        "resubmit": ParticipationStatus.resubmission_requested,
    }[decision]
    part.decided_by = decider.id
    part.decided_at = now_utc()
    part.approver_comment = comment
    db.flush()
    if decision == "approve":
        award_fn(db, part.id, decider.id)
    if do_notify:
        titles = {
            "approve": f"{label} approved",
            "reject": f"{label} rejected",
            "resubmit": f"Resubmission requested: {label}",
        }
        notify(db, part.user, notif_type, titles[decision], comment or titles[decision])


def seed_csr(db: Session, master, demo, employees) -> None:
    cats = list(master["csr_cats"].values())
    activities = []
    for i, title in enumerate(data.CSR_TITLES):
        if i < 10:
            status, start = CSRStatus.active, TODAY + dt.timedelta(days=rng.randint(3, 50))
        elif i < 16:
            status, start = CSRStatus.completed, dt.date(2026, rng.randint(4, 6), rng.randint(1, 25))
        elif i < 18:
            status, start = CSRStatus.draft, TODAY + dt.timedelta(days=rng.randint(30, 80))
        else:
            status, start = CSRStatus.archived, dt.date(2026, 2, rng.randint(1, 25))
        a = CSRActivity(
            title=title, description=fake.paragraph(5), category_id=rng.choice(cats).id,
            location=fake.city(), organizer_user_id=demo["esg"].id,
            capacity=rng.randint(15, 60), start_date=start,
            end_date=start + dt.timedelta(days=rng.randint(0, 2)),
            budget_inr=rng.randint(20, 200) * 1000, points=rng.choice([25, 50, 75, 100]),
            status=status, created_by=demo["esg"].id,
        )
        activities.append(a)
        db.add(a)
    db.flush()

    for a in activities:
        if a.status not in (CSRStatus.active, CSRStatus.completed):
            continue
        group = rng.sample(employees, rng.randint(4, 10))
        if a.status == CSRStatus.completed and demo["employee"] not in group and rng.random() < 0.7:
            group.append(demo["employee"])
        for u in group:
            part = CSRParticipation(activity_id=a.id, user_id=u.id)
            part.created_at = _dtime(a.start_date - dt.timedelta(days=rng.randint(3, 20)))
            db.add(part)
            db.flush()
            decider = responsible_head(db, u.department_id) or demo["admin"]
            if decider.id == u.id:
                decider = demo["admin"]
            do_notify = u.id == demo["employee"].id or rng.random() < 0.2
            if a.status == CSRStatus.completed:
                roll = rng.random()
                if roll < 0.7:
                    part.proof_attachment_id = _proof(db, u, "csr_participation").id
                    _decide(db, part, "approve", decider, "Great work at the event!",
                            award_once_for_csr, NotificationType.csr_decision, a.title, do_notify)
                elif roll < 0.8:
                    part.proof_attachment_id = _proof(db, u, "csr_participation").id
                    _decide(db, part, "reject", decider, "Proof does not show event participation.",
                            award_once_for_csr, NotificationType.csr_decision, a.title, do_notify)
                elif roll < 0.9:
                    part.proof_attachment_id = _proof(db, u, "csr_participation").id
                    _decide(db, part, "resubmit", decider, "Please upload a clearer photo with the team.",
                            award_once_for_csr, NotificationType.csr_decision, a.title, do_notify)
                else:
                    part.proof_attachment_id = _proof(db, u, "csr_participation").id
                    part.status = ParticipationStatus.submitted
            else:
                if rng.random() < 0.25:
                    part.proof_attachment_id = _proof(db, u, "csr_participation").id
                    part.status = ParticipationStatus.submitted
    db.flush()


def seed_challenges(db: Session, master, demo, employees) -> None:
    challenges = []
    statuses = [ChallengeStatus.active] * 4 + [ChallengeStatus.under_review] * 2 + \
               [ChallengeStatus.completed] * 2 + [ChallengeStatus.draft, ChallengeStatus.archived]
    for (title, cat, xp, diff, evidence), status in zip(data.CHALLENGES, statuses):
        c = Challenge(
            title=title, category_id=master["ch_cats"][cat].id, description=fake.paragraph(4),
            xp=xp, difficulty=Difficulty(diff), evidence=EvidenceMode(evidence),
            deadline=TODAY + dt.timedelta(days=rng.randint(20, 90))
            if status in (ChallengeStatus.active, ChallengeStatus.under_review, ChallengeStatus.draft)
            else dt.date(2026, 6, rng.randint(10, 30)),
            status=status, created_by=demo["esg"].id,
        )
        challenges.append(c)
        db.add(c)
    db.flush()

    for c in challenges:
        if c.status in (ChallengeStatus.draft, ChallengeStatus.archived):
            continue
        group = rng.sample(employees, rng.randint(5, 12))
        if c.status == ChallengeStatus.completed and demo["employee"] not in group and rng.random() < 0.8:
            group.append(demo["employee"])
        needs_proof = c.evidence == EvidenceMode.required or c.evidence == EvidenceMode.inherit
        for u in group:
            part = ChallengeParticipation(challenge_id=c.id, user_id=u.id)
            part.created_at = _dtime(TODAY - dt.timedelta(days=rng.randint(5, 80)))
            db.add(part)
            db.flush()
            decider = responsible_head(db, u.department_id) or demo["admin"]
            if decider.id == u.id:
                decider = demo["admin"]
            do_notify = u.id == demo["employee"].id or rng.random() < 0.2
            if c.status == ChallengeStatus.completed:
                roll = rng.random()
                if roll < 0.75:
                    if needs_proof:
                        part.proof_attachment_id = _proof(db, u, "challenge_participation").id
                    _decide(db, part, "approve", decider, "Verified — well done!",
                            award_once_for_challenge, NotificationType.challenge_decision,
                            c.title, do_notify)
                elif roll < 0.85:
                    part.proof_attachment_id = _proof(db, u, "challenge_participation").id
                    _decide(db, part, "reject", decider, "Logs do not cover the full period.",
                            award_once_for_challenge, NotificationType.challenge_decision,
                            c.title, do_notify)
                else:
                    part.proof_attachment_id = _proof(db, u, "challenge_participation").id
                    _decide(db, part, "resubmit", decider, "Please include the before/after readings.",
                            award_once_for_challenge, NotificationType.challenge_decision,
                            c.title, do_notify)
            elif c.status == ChallengeStatus.under_review:
                part.progress = rng.randint(60, 100)
                part.proof_attachment_id = _proof(db, u, "challenge_participation").id
                part.status = ParticipationStatus.submitted
            else:  # active
                part.progress = rng.randint(5, 80)
    db.flush()


def seed_redemptions(db: Session, master, demo, employees) -> None:
    rewards = master["rewards"]
    db.flush()
    rich = [u for u in employees if u.xp_balance >= 250][:8]
    if demo["employee"] not in rich and demo["employee"].xp_balance >= 100:
        rich.insert(0, demo["employee"])
    plans = [
        ("Steel Water Bottle", "placed"), ("Canvas Tote Bag", "placed"),
        ("Plant a Tree in Your Name", "fulfilled"), ("Organic Snack Box", "fulfilled"),
        ("Steel Water Bottle", "cancelled"), ("Bamboo Desk Kit", "returned"),
        ("Plant a Tree in Your Name", "placed"), ("Canvas Tote Bag", "fulfilled"),
    ]
    for user, (reward_name, final) in zip(rich, plans):
        reward = rewards[reward_name]
        if user.xp_balance < reward.points_cost or reward.stock < 1:
            continue
        redemption = redeem_reward(db, user, reward.id)
        if final in ("fulfilled", "returned"):
            fulfill_redemption(db, redemption, demo["esg"].id)
        if final == "returned":
            return_redemption(db, redemption, demo["esg"].id)
        if final == "cancelled":
            cancel_redemption(db, redemption, user.id)
    db.flush()


def seed_governance(db: Session, depts, demo) -> None:
    for title, severity, dept_name, key in data.COMPLIANCE_ISSUES:
        dept = depts[dept_name]
        owner = responsible_head(db, dept.id) or demo["esg"]
        if key.startswith("overdue"):
            due = TODAY - dt.timedelta(days=rng.randint(4, 30))
            status = IssueStatus.open if key == "overdue_open" else IssueStatus.in_progress
            resolved_at = None
        elif key == "open":
            due, status, resolved_at = TODAY + dt.timedelta(days=rng.randint(20, 60)), IssueStatus.open, None
        elif key == "in_progress":
            due, status, resolved_at = TODAY + dt.timedelta(days=rng.randint(10, 45)), IssueStatus.in_progress, None
        else:
            due = TODAY - dt.timedelta(days=rng.randint(15, 50))
            status = IssueStatus.resolved if key == "resolved" else IssueStatus.closed
            resolved_at = _dtime(due - dt.timedelta(days=rng.randint(1, 8)))
        db.add(ComplianceIssue(
            title=title, description=fake.paragraph(3), severity=Severity(severity),
            owner_user_id=owner.id, due_date=due, status=status, department_id=dept.id,
            resolved_at=resolved_at, created_by=demo["esg"].id,
        ))
    db.flush()
    flagged = run_overdue_check(db)  # fires overdue notifications + audit entries
    print(f"  overdue issues flagged + notified: {flagged}")

    audit_rows = [
        ("Internal ESG Audit — FY26 close", "Manufacturing", 84, AuditStatus.completed),
        ("Fire & Safety Compliance Audit", "Assembly Line", 76, AuditStatus.completed),
        ("Energy Efficiency Audit", "Operations", 91, AuditStatus.completed),
        ("Supplier Governance Review", "Sales & Marketing", 62, AuditStatus.completed),
        ("Q2 FY27 Surveillance Audit", "Sustainability & ESG", None, AuditStatus.planned),
    ]
    for title, dept_name, score, status in audit_rows:
        db.add(Audit(
            title=title, auditor_name=fake.name(), auditor_user_id=demo["esg"].id,
            scope_note=f"{dept_name} — processes, records and controls",
            department_id=depts[dept_name].id,
            audit_date=dt.date(2026, rng.randint(4, 6), rng.randint(3, 27))
            if status == AuditStatus.completed else TODAY + dt.timedelta(days=30),
            findings=fake.paragraph(4) if status == AuditStatus.completed else "",
            score=score, status=status,
        ))
    db.flush()


def spread_xp_dates(db: Session) -> None:
    """Distribute XP-ledger timestamps over ~75 days so leaderboard periods differ."""
    txns = db.query(XPTransaction).order_by(XPTransaction.id).all()
    if not txns:
        return
    start = now_utc() - dt.timedelta(days=75)
    step = dt.timedelta(days=75) / max(len(txns), 1)
    for i, txn in enumerate(txns):
        txn.created_at = start + step * i
    db.flush()


def run() -> None:
    print("EcoSphere seed: wiping schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        get_org_settings(db)
        depts, demo, employees = seed_users_departments(db)
        print(f"  departments: {len(depts)}, users: {db.query(User).count()}")
        master = seed_master(db, depts, demo)
        ops = seed_erp_carbon(db, depts, demo, master["factors"])
        print(f"  ERP operations + auto carbon transactions: {ops}")
        all_users = db.query(User).all()
        seed_policies_trainings(db, demo, all_users)
        seed_csr(db, master, demo, employees)
        seed_challenges(db, master, demo, employees)
        db.flush()
        db.expire_all()
        seed_redemptions(db, master, demo, employees)
        assign_badge_manual(db, demo["head"], master["badges"]["Founder's Award"], demo["admin"].id)
        assign_badge_manual(db, demo["employee"], master["badges"]["Green Innovator"], demo["admin"].id)
        awarded = sweep_all(db)
        print(f"  automatic badges awarded: {awarded}")
        seed_governance(db, depts, demo)
        spread_xp_dates(db)
        db.commit()
        print("Seed complete.\n")
        print("Demo accounts (password for all: %s)" % data.DEMO_PASSWORD)
        print("  Admin        admin@ecosphere.in")
        print("  ESG Manager  esg@ecosphere.in")
        print("  Dept Head    head@ecosphere.in   (Manufacturing)")
        print("  Employee     employee@ecosphere.in (Priya Sharma, Manufacturing)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
