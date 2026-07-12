import datetime as dt
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, or_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.core import Department, User, Notification
from app.models.enums import ActiveStatus, Gender, Role, Scope, IssueStatus, Severity, NotificationType
from app.models.governance import ComplianceIssue, Audit
from app.models.risk import DepartmentRiskSnapshot, RiskAlert
from app.services.risk_engine import recalculate_department_risk


class RiskHeatmapApiTestCase(unittest.TestCase):
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
        with self.Session() as db:
            # Create Users
            self.admin = User(
                employee_code="ADM-001",
                email="admin@example.com",
                password_hash=hash_password("AdminPass123"),
                full_name="Platform Admin",
                role=Role.admin,
                gender=Gender.other,
                is_active=True,
            )
            self.esg = User(
                employee_code="ESG-001",
                email="esg@example.com",
                password_hash=hash_password("EsgPass123"),
                full_name="ESG Manager",
                role=Role.esg_manager,
                gender=Gender.male,
                is_active=True,
            )
            self.employee = User(
                employee_code="EMP-001",
                email="emp@example.com",
                password_hash=hash_password("EmpPass123"),
                full_name="Priya Sharma",
                role=Role.employee,
                gender=Gender.female,
                is_active=True,
            )
            db.add_all([self.admin, self.esg, self.employee])
            db.flush()

            # Create Department
            self.dept = Department(name="Manufacturing", head_user_id=self.admin.id, status=ActiveStatus.active)
            db.add(self.dept)
            db.flush()

            # Set department_id
            self.admin.department_id = self.dept.id
            self.employee.department_id = self.dept.id
            db.flush()

            self.admin_id = self.admin.id
            self.esg_id = self.esg.id
            self.employee_id = self.employee.id
            self.dept_id = self.dept.id
            db.commit()

        self.admin_headers = self._auth_headers(self.admin_id, Role.admin)
        self.esg_headers = self._auth_headers(self.esg_id, Role.esg_manager)

    @staticmethod
    def _auth_headers(user_id: int, role: Role) -> dict[str, str]:
        token = create_access_token(user_id, role.value)
        return {"Authorization": f"Bearer {token}"}

    def test_compliance_issue_lifecycle(self):
        # 1. Create a compliance issue
        payload = {
            "title": "Diesel emission permit missing",
            "description": "The generator permit expired last week",
            "severity": "critical",
            "owner_user_id": self.employee_id,
            "due_date": "2026-04-12",
            "department_id": self.dept_id,
        }
        res = self.client.post("/api/v1/compliance/issues", json=payload, headers=self.esg_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["title"], "Diesel emission permit missing")
        self.assertEqual(data["status"], "open")
        self.assertFalse(data["is_overdue"])

        # Check notifications were sent
        with self.Session() as db:
            notifs = db.execute(
                select(Notification).where(Notification.type == NotificationType.compliance_new)
            ).scalars().all()
            self.assertTrue(len(notifs) > 0)

        # 2. Update status (open -> in_progress)
        update_payload = {"status": "in_progress"}
        res = self.client.patch(
            f"/api/v1/compliance/issues/{data['id']}", json=update_payload, headers=self.admin_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "in_progress")

        # 3. Invalid transition (in_progress -> closed is invalid for admin but they bypass, wait - admins bypass transition checks!)
        # Let's verify non-admin owner trying to transition in_progress -> closed
        regular_headers = self._auth_headers(self.employee_id, Role.employee)
        res = self.client.patch(
            f"/api/v1/compliance/issues/{data['id']}", json={"status": "closed"}, headers=regular_headers
        )
        self.assertEqual(res.status_code, 400)

        # 4. Unauthorized update (employee trying to update an issue they don't own, let's change owner first to admin)
        # We will create a separate issue owned by admin
        payload2 = {
            "title": "Admin issue",
            "description": "owned by admin",
            "severity": "medium",
            "owner_user_id": self.admin_id,
            "due_date": "2026-04-12",
            "department_id": self.dept_id,
        }
        res2 = self.client.post("/api/v1/compliance/issues", json=payload2, headers=self.esg_headers)
        issue2_id = res2.json()["id"]

        # Employee (non-owner, non-head) tries to edit it
        res3 = self.client.patch(
            f"/api/v1/compliance/issues/{issue2_id}", json={"title": "Hacked Title"}, headers=regular_headers
        )
        self.assertEqual(res3.status_code, 403)

    def test_risk_recalculation_and_snapshot(self):
        # Recalculate department risk
        with self.Session() as db:
            snap = recalculate_department_risk(db, self.dept_id, dt.date(2026, 4, 12))
            db.commit()
            
            # Environmental = 0, Social: participation=20 (0%), training=0 (no trainings), inactive=15 (100% inactive) -> Total 35/55 * 100 = 63.63
            # Gov: policy=0, issues=0, audit=0
            # Overall = 0.4 * 0 + 0.3 * 63.63 + 0.3 * 0 = 19.09
            self.assertAlmostEqual(snap.overall_risk, 19.09, places=1)

    def test_risk_heatmap_dashboard_and_drilldown(self):
        # Seed historical snapshots
        with self.Session() as db:
            snap1 = DepartmentRiskSnapshot(
                department_id=self.dept_id,
                snapshot_date=dt.date(2026, 3, 28),
                environmental_risk=45.0,
                social_risk=30.0,
                governance_risk=20.0,
                overall_risk=33.0,
            )
            snap2 = DepartmentRiskSnapshot(
                department_id=self.dept_id,
                snapshot_date=dt.date(2026, 4, 28),
                environmental_risk=65.0,
                social_risk=40.0,
                governance_risk=35.0,
                overall_risk=48.5,
            )
            db.add_all([snap1, snap2])
            db.commit()

        # Fetch heatmap
        res = self.client.get("/api/v1/risk-heatmap", headers=self.esg_headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(len(res.json()) > 0)

        # Fetch dashboard
        res = self.client.get("/api/v1/risk-heatmap/dashboard", headers=self.esg_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["highest_risk_department"]["name"], "Manufacturing")

        # Fetch drilldown
        res = self.client.get(f"/api/v1/risk-heatmap/drilldown/{self.dept_id}", headers=self.esg_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("ai_insight", res.json())
        self.assertTrue(len(res.json()["contributors"]) > 0)
