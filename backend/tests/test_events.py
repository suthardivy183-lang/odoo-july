import datetime as dt
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.carbon_accounting import (
    CarbonCostEntry,
    CarbonPricingRule,
    DepartmentCarbonBudget,
    PricingMethod,
)
from app.models.core import Department, Notification, User
from app.models.enums import ActiveStatus, ERPType, Gender, Role, Scope
from app.models.events import DomainEvent
from app.models.masterdata import EmissionFactor
from app.models.risk import DepartmentRiskSnapshot, RiskAlert


class EventSpineApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(bind=cls.engine, expire_on_commit=False)

        def override_db():
            with cls.Session() as db:
                yield db

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
            manager = User(
                employee_code="ESG-EVENT",
                email="events-esg@example.com",
                password_hash=hash_password("Password123"),
                full_name="ESG Event Manager",
                role=Role.esg_manager,
                gender=Gender.other,
                is_active=True,
            )
            head = User(
                employee_code="HEAD-EVENT",
                email="events-head@example.com",
                password_hash=hash_password("Password123"),
                full_name="Department Head",
                role=Role.dept_head,
                gender=Gender.other,
                is_active=True,
            )
            db.add_all([manager, head])
            db.flush()
            dept = Department(name="Event Manufacturing", head_user_id=head.id)
            db.add(dept)
            db.flush()
            factor = EmissionFactor(
                name="Diesel purchase event factor",
                source_type=ERPType.purchase,
                unit="L",
                factor_value=2.68,
                scope=Scope.scope1,
                effective_date=dt.date(2026, 4, 1),
                version=1,
                status=ActiveStatus.active,
            )
            db.add(factor)
            db.flush()
            db.add(
                CarbonPricingRule(
                    price_per_ton=4000,
                    currency="INR",
                    effective_date=dt.date(2026, 4, 1),
                    pricing_method=PricingMethod.fixed_internal,
                    is_active=True,
                    version=1,
                )
            )
            db.add(
                DepartmentCarbonBudget(
                    department_id=dept.id,
                    fiscal_year="2026-2027",
                    period_type="annual",
                    budgeted_co2e_tons=0.01,
                    start_date=dt.date(2026, 4, 1),
                    end_date=dt.date(2027, 3, 31),
                    created_by=manager.id,
                )
            )
            db.commit()
            self.manager_id = manager.id
            self.dept_id = dept.id
        token = create_access_token(self.manager_id, Role.esg_manager.value)
        self.headers = {"Authorization": f"Bearer {token}"}

    def test_over_budget_erp_operation_completes_risk_spine_in_one_commit(self):
        response = self.client.post(
            "/api/v1/erp/operations",
            headers=self.headers,
            json={
                "op_type": "purchase",
                "department_id": self.dept_id,
                "op_date": "2026-07-12",
                "reference_no": "ERP-EVENT-001",
                "lines": [{"resource": "Diesel", "quantity": 100, "unit": "L"}],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)

        with self.Session() as db:
            self.assertEqual(db.scalar(select(func.count(CarbonCostEntry.id))), 1)
            self.assertEqual(db.scalar(select(func.count(RiskAlert.id))), 1)
            self.assertGreaterEqual(db.scalar(select(func.count(Notification.id))), 2)
            self.assertEqual(db.scalar(select(func.count(DepartmentRiskSnapshot.id))), 1)
            types = list(db.scalars(select(DomainEvent.type)).all())
            self.assertGreaterEqual(len(types), 3)
            self.assertIn("carbon.txn.created", types)
            self.assertIn("carbon.budget.exceeded", types)
            self.assertIn("risk.snapshot.updated", types)

        recent = self.client.get(
            f"/api/v1/events/recent?department_id={self.dept_id}&limit=3",
            headers=self.headers,
        )
        self.assertEqual(recent.status_code, 200, recent.text)
        self.assertEqual(len(recent.json()), 3)

    def test_heatmap_get_is_a_pure_snapshot_read(self):
        recalc = self.client.post("/api/v1/risk-heatmap/recalculate", headers=self.headers)
        self.assertEqual(recalc.status_code, 200, recalc.text)

        writes = 0

        def count_writes(_conn, _cursor, statement, _parameters, _context, _many):
            nonlocal writes
            if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
                writes += 1

        event.listen(self.engine, "before_cursor_execute", count_writes)
        try:
            response = self.client.get("/api/v1/risk-heatmap", headers=self.headers)
        finally:
            event.remove(self.engine, "before_cursor_execute", count_writes)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(writes, 0)
        self.assertEqual(len(response.json()), 1)


if __name__ == "__main__":
    unittest.main()
