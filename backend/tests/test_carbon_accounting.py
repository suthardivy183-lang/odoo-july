import datetime as dt
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.core import Department, User
from app.models.enums import ActiveStatus, Gender, Role, Scope
from app.models.masterdata import EmissionFactor
from app.models.carbon_accounting import (
    CarbonPricingRule,
    CarbonCostEntry,
    DepartmentCarbonBudget,
    PricingMethod,
)
from app.models.environment import CarbonTransaction


class CarbonAccountingApiTestCase(unittest.TestCase):
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
            db.add_all([self.admin, self.esg])
            db.flush()

            # Create Department
            self.dept = Department(name="Manufacturing", head_user_id=self.admin.id)
            db.add(self.dept)
            db.flush()

            # Create Emission Factor
            self.factor = EmissionFactor(
                name="Diesel (Purchase)",
                source_type="purchase",
                unit="L",
                factor_value=2.68,
                scope=Scope.scope1,
                effective_date=dt.date(2026, 4, 1),
                version=1,
                status=ActiveStatus.active,
            )
            db.add(self.factor)
            db.flush()

            self.admin_id = self.admin.id
            self.esg_id = self.esg.id
            self.dept_id = self.dept.id
            self.factor_id = self.factor.id
            db.commit()

        self.admin_headers = self._auth_headers(self.admin_id, Role.admin)
        self.esg_headers = self._auth_headers(self.esg_id, Role.esg_manager)

    @staticmethod
    def _auth_headers(user_id: int, role: Role) -> dict[str, str]:
        token = create_access_token(user_id, role.value)
        return {"Authorization": f"Bearer {token}"}

    def test_pricing_rule_lifecycle(self):
        # 1. Create a pricing rule (ESG manager)
        payload = {
            "price_per_ton": 3500.0,
            "currency": "INR",
            "effective_date": "2026-04-01",
            "pricing_method": "fixed_internal",
            "is_active": True,
        }
        res = self.client.post(
            "/api/v1/carbon/pricing-rules", json=payload, headers=self.esg_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["price_per_ton"], 3500.0)
        self.assertTrue(data["is_active"])
        self.assertEqual(data["version"], 1)

        # 2. Get active pricing rule
        res = self.client.get("/api/v1/carbon/pricing-rules/active")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["price_per_ton"], 3500.0)

        # 3. Create another pricing rule (should deactivate the first one)
        payload = {
            "price_per_ton": 4000.0,
            "currency": "INR",
            "effective_date": "2026-05-01",
            "pricing_method": "govt_tax",
            "is_active": True,
        }
        res = self.client.post(
            "/api/v1/carbon/pricing-rules", json=payload, headers=self.esg_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["version"], 2)

        # Check that v1 is now inactive
        with self.Session() as db:
            r1 = db.get(CarbonPricingRule, 1)
            self.assertFalse(r1.is_active)
            r2 = db.get(CarbonPricingRule, 2)
            self.assertTrue(r2.is_active)

    def test_carbon_transaction_cost_calculation(self):
        # Create active pricing rule
        with self.Session() as db:
            rule = CarbonPricingRule(
                price_per_ton=4000.0,
                currency="INR",
                effective_date=dt.date(2026, 4, 1),
                pricing_method=PricingMethod.fixed_internal,
                is_active=True,
                version=1,
            )
            db.add(rule)
            db.commit()

        # Create carbon transaction
        payload = {
            "department_id": self.dept_id,
            "activity_date": "2026-04-12",
            "description": "Diesel purchase for generators",
            "quantity": 100.0,
            "unit": "L",
            "emission_factor_id": self.factor_id,
            "notes": "Test notes",
        }
        res = self.client.post(
            "/api/v1/carbon/transactions", json=payload, headers=self.esg_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["co2e_kg"], 268.0)  # 100 * 2.68

        # Verify cost entry was created
        with self.Session() as db:
            cost = db.execute(
                select(CarbonCostEntry).where(
                    CarbonCostEntry.carbon_transaction_id == data["id"]
                )
            ).scalar_one()
            self.assertEqual(float(cost.price_per_ton_used), 4000.0)
            self.assertEqual(float(cost.co2e_kg), 268.0)
            # 268kg = 0.268 tons * 4000 = 1072.0
            self.assertEqual(float(cost.financial_liability), 1072.0)

    def test_budget_utilization(self):
        # Create budget
        payload = {
            "department_id": self.dept_id,
            "fiscal_year": "2026-2027",
            "period_type": "annual",
            "period_value": None,
            "budgeted_co2e_tons": 10.0,
            "start_date": "2026-04-01",
            "end_date": "2027-03-31",
        }
        res = self.client.post(
            "/api/v1/carbon/budgets", json=payload, headers=self.admin_headers
        )
        self.assertEqual(res.status_code, 200)

        # Create a transaction
        with self.Session() as db:
            rule = CarbonPricingRule(
                price_per_ton=3500.0,
                currency="INR",
                effective_date=dt.date(2026, 4, 1),
                pricing_method=PricingMethod.fixed_internal,
                is_active=True,
            )
            db.add(rule)
            db.flush()

            tx = CarbonTransaction(
                department_id=self.dept_id,
                activity_date=dt.date(2026, 5, 10),
                description="Diesel purchase",
                quantity=1000.0,  # 1000 L * 2.68 = 2680kg = 2.68 tons
                unit="L",
                emission_factor_id=self.factor_id,
                factor_value_snapshot=2.68,
                factor_version_snapshot=1,
                co2e_kg=2680.0,
                scope=Scope.scope1,
            )
            db.add(tx)
            db.flush()

            # calculate cost
            cost = CarbonCostEntry(
                carbon_transaction_id=tx.id,
                pricing_rule_id=rule.id,
                co2e_kg=2680.0,
                price_per_ton_used=3500.0,
                financial_liability=9380.0,  # 2.68 * 3500
                currency="INR",
            )
            db.add(cost)
            db.commit()

        # Check budgets list
        res = self.client.get("/api/v1/carbon/budgets", headers=self.esg_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["items"][0]
        self.assertEqual(data["actual_co2e_tons"], 2.68)
        self.assertEqual(data["budget_utilization_pct"], 26.8)
        self.assertEqual(data["estimated_liability"], 9380.0)

    def test_scenario_simulation(self):
        # Create some baseline transactions
        with self.Session() as db:
            # 1. Diesel purchase (Purchase)
            tx1 = CarbonTransaction(
                department_id=self.dept_id,
                activity_date=dt.date.today() - dt.timedelta(days=10),
                description="Diesel for generator",
                quantity=1000.0,
                unit="L",
                emission_factor_id=self.factor_id,
                factor_value_snapshot=2.68,
                factor_version_snapshot=1,
                co2e_kg=2680.0,  # 2.68 tons
                scope=Scope.scope1,
            )
            db.add(tx1)
            db.commit()

        payload = {
            "diesel_reduction_pct": 20.0,
            "fleet_ev_pct": 0.0,
            "solar_replacement_pct": 0.0,
        }
        res = self.client.post(
            "/api/v1/carbon/accounting/simulate", json=payload, headers=self.esg_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # 20% of 2.68 tons = 0.536 tons (rounds to 0.54)
        self.assertAlmostEqual(data["carbon_reduction_tons"], 0.54, places=2)
        self.assertEqual(data["carbon_reduction_pct"], 20.0)

    def test_reports_generation(self):
        # Test CSV export
        res = self.client.get(
            "/api/v1/carbon/accounting/reports?report_type=monthly_cost&file_format=csv",
            headers=self.esg_headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers["content-type"])
        self.assertIn(
            "attachment; filename=monthly_cost.csv", res.headers["content-disposition"]
        )

        # Test Excel export
        res = self.client.get(
            "/api/v1/carbon/accounting/reports?report_type=monthly_cost&file_format=excel",
            headers=self.esg_headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            res.headers["content-type"],
        )

        # Test PDF export
        res = self.client.get(
            "/api/v1/carbon/accounting/reports?report_type=monthly_cost&file_format=pdf",
            headers=self.esg_headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("application/pdf", res.headers["content-type"])
