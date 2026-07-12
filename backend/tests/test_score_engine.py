import datetime as dt
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.core import Department, User
from app.models.enums import (
    AuditStatus,
    Gender,
    GoalStatus,
    IssueStatus,
    ParticipationStatus,
    PolicyStatus,
    Role,
    Scope,
    Severity,
    TrainingStatus,
)
from app.models.environment import CarbonTransaction
from app.models.governance import Audit, ComplianceIssue
from app.models.masterdata import (
    EmissionFactor,
    EnvironmentalGoal,
    ESGPolicy,
    PolicyAcknowledgement,
    Training,
    TrainingCompletion,
)
from app.models.social import CSRActivity, CSRParticipation
from app.models.masterdata import Category
from app.models.enums import CategoryType, ERPType
from app.services import score_engine
from app.utils.time import today_ist


class PureAggregationTests(unittest.TestCase):
    def test_pillar_mean_excludes_none_and_never_zero(self):
        self.assertEqual(score_engine.pillar_mean([50, None, 100]), 75)
        self.assertEqual(score_engine.pillar_mean([80]), 80)
        self.assertIsNone(score_engine.pillar_mean([None, None]))

    def test_weighted_total_renormalizes_over_available_weights(self):
        weights = {"environmental": 40, "social": 30, "governance": 30}
        # all present -> straight weighted average
        self.assertAlmostEqual(
            score_engine.weighted_total(50, 60, 70, weights), (40 * 50 + 30 * 60 + 30 * 70) / 100
        )
        # governance missing -> denominator becomes 70, not 100
        self.assertAlmostEqual(
            score_engine.weighted_total(50, 60, None, weights), (40 * 50 + 30 * 60) / 70
        )
        # only one pillar present -> equals that pillar
        self.assertAlmostEqual(score_engine.weighted_total(None, 60, None, weights), 60)
        # nothing present -> 0
        self.assertEqual(score_engine.weighted_total(None, None, None, weights), 0.0)


class ScoreEngineDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(bind=cls.engine, expire_on_commit=False)

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.wide_start = dt.date(2000, 1, 1)
        self.wide_end = today_ist()
        with self.Session() as db:
            # Departments: A (scoreable), B (scoreable), C (no employees -> excluded)
            dept_a = Department(name="Alpha")
            dept_b = Department(name="Bravo")
            dept_c = Department(name="Empty")
            db.add_all([dept_a, dept_b, dept_c])
            db.flush()

            # head of Alpha (for API scoping test)
            head = User(
                employee_code="HEAD-A", email="head-a@x.com",
                password_hash=hash_password("x"), full_name="Head A",
                role=Role.dept_head, gender=Gender.male, department_id=dept_a.id,
            )
            db.add(head)
            db.flush()
            dept_a.head_user_id = head.id

            # Alpha: head(male) + 1 female = 2 active employees, mixed gender -> diversity 100
            a2 = User(
                employee_code="A2", email="a2@x.com", password_hash=hash_password("x"),
                full_name="A Two", role=Role.employee, gender=Gender.female,
                department_id=dept_a.id,
            )
            # Bravo: 2 male employees -> diversity 0
            b1 = User(
                employee_code="B1", email="b1@x.com", password_hash=hash_password("x"),
                full_name="B One", role=Role.employee, gender=Gender.male,
                department_id=dept_b.id,
            )
            b2 = User(
                employee_code="B2", email="b2@x.com", password_hash=hash_password("x"),
                full_name="B Two", role=Role.employee, gender=Gender.male,
                department_id=dept_b.id,
            )
            db.add_all([a2, b1, b2])
            db.flush()

            # Emissions: Alpha 1000 kg (500/emp), Bravo 0 -> min-max: Alpha 0, Bravo 100
            factor = EmissionFactor(
                name="F", source_type=ERPType.purchase, unit="kg", factor_value=1,
                scope=Scope.scope1, effective_date=today_ist(),
            )
            db.add(factor)
            db.flush()
            db.add(CarbonTransaction(
                department_id=dept_a.id, activity_date=today_ist(), description="e",
                quantity=1000, unit="kg", emission_factor_id=factor.id,
                factor_value_snapshot=1, factor_version_snapshot=1, co2e_kg=1000,
                scope=Scope.scope1, is_auto=False,
            ))

            # Goal: Alpha one active goal at 50% progress; Bravo none -> excluded
            db.add(EnvironmentalGoal(
                name="g", metric_unit="kg", baseline_value=0, target_value=100,
                current_value=50, deadline=today_ist(), owner_department_id=dept_a.id,
                status=GoalStatus.active,
            ))

            # CSR: one approved participation by an Alpha employee -> 1/2 = 50%
            cat = Category(name="Env", type=CategoryType.csr)
            db.add(cat)
            db.flush()
            csr = CSRActivity(
                title="c", category_id=cat.id, location="x",
                start_date=today_ist(), end_date=today_ist(),
            )
            db.add(csr)
            db.flush()
            db.add(CSRParticipation(
                activity_id=csr.id, user_id=a2.id, status=ParticipationStatus.approved,
            ))

            # Training: 1 active; Alpha 1 completion (required 2) -> 50%; Bravo 0
            training = Training(name="t", status=TrainingStatus.active)
            db.add(training)
            db.flush()
            db.add(TrainingCompletion(training_id=training.id, user_id=a2.id))

            # Policy: 1 published v1; Alpha 1 ack (required 2) -> 50%; Bravo 0
            policy = ESGPolicy(title="p", body="b", status=PolicyStatus.published, version=1)
            db.add(policy)
            db.flush()
            db.add(PolicyAcknowledgement(policy_id=policy.id, policy_version=1, user_id=a2.id))

            # Audit: Alpha one completed score 80; Bravo none -> excluded
            db.add(Audit(
                title="au", auditor_name="x", department_id=dept_a.id,
                audit_date=today_ist(), score=80, status=AuditStatus.completed,
            ))

            # Compliance: Alpha one open overdue issue -> health 0; Bravo none -> 100
            db.add(ComplianceIssue(
                title="i", severity=Severity.high, owner_user_id=a2.id,
                due_date=today_ist() - dt.timedelta(days=10), status=IssueStatus.open,
                department_id=dept_a.id,
            ))
            db.commit()

            self.dept_a = dept_a.id
            self.dept_b = dept_b.id
            self.dept_c = dept_c.id
            self.head_id = head.id

    def _scores(self):
        with self.Session() as db:
            return score_engine.compute_all_departments(db, self.wide_start, self.wide_end)

    def test_zero_employee_department_is_excluded(self):
        scores = self._scores()
        self.assertIn(self.dept_a, scores)
        self.assertIn(self.dept_b, scores)
        self.assertNotIn(self.dept_c, scores)

    def test_emission_performance_min_max_normalization(self):
        scores = self._scores()
        comp = {c.key: c.value for c in scores[self.dept_a].components}
        compb = {c.key: c.value for c in scores[self.dept_b].components}
        self.assertAlmostEqual(comp["emission_performance"], 0.0)   # highest emitter
        self.assertAlmostEqual(compb["emission_performance"], 100.0)  # lowest emitter

    def test_no_data_components_excluded_from_pillar(self):
        scores = self._scores()
        # Bravo has no goals -> goal_completion None -> Environmental = emission only (100)
        compb = {c.key: c.value for c in scores[self.dept_b].components}
        self.assertIsNone(compb["goal_completion"])
        self.assertAlmostEqual(scores[self.dept_b].environmental, 100.0)
        # Alpha Environmental = mean(goal 50, emission 0) = 25
        self.assertAlmostEqual(scores[self.dept_a].environmental, 25.0)

    def test_diversity_and_compliance_health(self):
        scores = self._scores()
        ca = {c.key: c.value for c in scores[self.dept_a].components}
        cb = {c.key: c.value for c in scores[self.dept_b].components}
        self.assertAlmostEqual(ca["diversity_balance"], 100.0)  # 1M1F
        self.assertAlmostEqual(cb["diversity_balance"], 0.0)    # 2M
        self.assertAlmostEqual(ca["compliance_health"], 0.0)    # 1 overdue open, floored
        self.assertAlmostEqual(cb["compliance_health"], 100.0)  # no issues

    def test_department_and_org_totals(self):
        scores = self._scores()
        # Alpha: E25 S66.67 G43.33 -> 43.0
        # Bravo: E100 S0 G=mean(policy_ack 0, audit None, health 100)=50 -> 55.0
        self.assertAlmostEqual(scores[self.dept_a].total, 43.0, places=1)
        self.assertAlmostEqual(scores[self.dept_b].total, 55.0, places=1)
        with self.Session() as db:
            org = score_engine.compute_org_score(db, self.wide_start, self.wide_end)
        # employee-weighted: (43*2 + 55*2)/4 = 49.0
        self.assertAlmostEqual(org.total, 49.0, places=1)
        self.assertEqual(org.dept_count, 2)

    def test_department_head_scoped_to_managed_departments(self):
        token = create_access_token(self.head_id, Role.dept_head.value)
        resp = self.client.get(
            "/api/v1/scores/departments?period=all",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        returned = {d["department_id"] for d in resp.json()}
        self.assertEqual(returned, {self.dept_a})

    def test_snapshot_scores_persists_org_and_dept_rows(self):
        with self.Session() as db:
            org = score_engine.snapshot_scores(db)
            db.commit()
            from app.models.scores import DepartmentScoreSnapshot, OrgScoreSnapshot
            from sqlalchemy import select

            org_rows = db.execute(select(OrgScoreSnapshot)).scalars().all()
            dept_rows = db.execute(select(DepartmentScoreSnapshot)).scalars().all()
        self.assertEqual(len(org_rows), 1)
        self.assertEqual(len(dept_rows), 2)  # only scoreable depts
        self.assertAlmostEqual(org.total, 49.0, places=1)


if __name__ == "__main__":
    unittest.main()
