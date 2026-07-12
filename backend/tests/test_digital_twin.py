import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.core import Department, User
from app.models.enums import ERPType, Gender, Role, Scope
from app.models.environment import CarbonTransaction
from app.models.masterdata import EmissionFactor
from app.utils.time import today_ist


class DigitalTwinApiTestCase(unittest.TestCase):
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
            admin = User(
                employee_code="ADM-TWIN",
                email="twin-admin@example.com",
                password_hash=hash_password("AdminPass123"),
                full_name="Twin Admin",
                role=Role.admin,
                gender=Gender.other,
                is_active=True,
            )
            employee = User(
                employee_code="EMP-TWIN",
                email="twin-employee@example.com",
                password_hash=hash_password("EmployeePass123"),
                full_name="Twin Employee",
                role=Role.employee,
                gender=Gender.other,
                is_active=True,
            )
            department = Department(name="Digital Twin Lab")
            factors = [
                EmissionFactor(
                    name=f"Factor {scope.value}",
                    source_type=ERPType.purchase,
                    unit="kg",
                    factor_value=1,
                    scope=scope,
                    effective_date=today_ist(),
                )
                for scope in (Scope.scope1, Scope.scope2, Scope.scope3)
            ]
            db.add_all([admin, employee, department, *factors])
            db.flush()
            for amount, scope, factor in zip(
                (300_000, 300_000, 400_000),
                (Scope.scope1, Scope.scope2, Scope.scope3),
                factors,
            ):
                db.add(
                    CarbonTransaction(
                        department_id=department.id,
                        activity_date=today_ist(),
                        description=f"{scope.value} annual footprint",
                        quantity=amount,
                        unit="kg",
                        emission_factor_id=factor.id,
                        factor_value_snapshot=1,
                        factor_version_snapshot=1,
                        co2e_kg=amount,
                        scope=scope,
                        is_auto=False,
                        created_by=admin.id,
                    )
                )
            db.commit()
            self.admin_id = admin.id
            self.employee_id = employee.id

        self.admin_headers = self._headers(self.admin_id, Role.admin)
        self.employee_headers = self._headers(self.employee_id, Role.employee)

    @staticmethod
    def _headers(user_id: int, role: Role) -> dict[str, str]:
        token = create_access_token(user_id, role.value)
        return {"Authorization": f"Bearer {token}"}

    def test_combined_scenario_returns_score_carbon_savings_and_breakdown(self):
        response = self.client.post(
            "/api/v1/scores/simulate",
            headers=self.admin_headers,
            json={
                "current_esg_score": 72,
                "fleet_electrification_pct": 50,
                "remote_employee_pct": 30,
                "remote_days_per_week": 2,
                "supplier_switch_pct": 30,
                "supplier_emissions_improvement_pct": 30,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["data_source"], "live_ledger")
        self.assertEqual(body["current_carbon_kg"], 1_000_000)
        self.assertAlmostEqual(body["carbon_reduction_kg"], 174_000)
        self.assertAlmostEqual(body["carbon_reduction_pct"], 17.4)
        self.assertAlmostEqual(body["scenario_esg_score"], 80.7)
        self.assertAlmostEqual(body["annual_savings_inr"], 3_132_000)
        self.assertEqual(
            [item["key"] for item in body["breakdown"]], ["fleet", "remote", "supplier"]
        )
        self.assertEqual(body["projection"][-1]["scenario_carbon_kg"], 826_000)

    def test_no_ledger_uses_disclosed_demo_baseline(self):
        with self.Session() as db:
            db.execute(delete(CarbonTransaction))
            db.commit()

        response = self.client.post(
            "/api/v1/scores/simulate",
            headers=self.admin_headers,
            json={"fleet_electrification_pct": 0},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data_source"], "demo_baseline")
        self.assertEqual(response.json()["current_carbon_kg"], 1_000_000)

    def test_employee_cannot_run_decision_simulation(self):
        response = self.client.post(
            "/api/v1/scores/simulate",
            headers=self.employee_headers,
            json={"fleet_electrification_pct": 50},
        )

        self.assertEqual(response.status_code, 403, response.text)


if __name__ == "__main__":
    unittest.main()
