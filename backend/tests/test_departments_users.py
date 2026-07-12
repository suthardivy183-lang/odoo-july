import datetime as dt
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import Base, get_db
from app.main import app
from app.models.core import AuditLog, Department, User
from app.models.enums import ActiveStatus, AuditAction, Gender, Role


class DepartmentUserApiTestCase(unittest.TestCase):
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
            self.admin = User(
                employee_code="ADM-001",
                email="admin@example.com",
                password_hash=hash_password("AdminPass123"),
                full_name="Platform Admin",
                role=Role.admin,
                gender=Gender.other,
                is_active=True,
            )
            self.head = User(
                employee_code="HEAD-001",
                email="head@example.com",
                password_hash=hash_password("HeadPass123"),
                full_name="Department Head",
                role=Role.dept_head,
                gender=Gender.female,
                is_active=True,
            )
            self.employee = User(
                employee_code="EMP-001",
                email="employee@example.com",
                password_hash=hash_password("EmployeePass123"),
                full_name="Active Employee",
                role=Role.employee,
                gender=Gender.male,
                is_active=True,
            )
            db.add_all([self.admin, self.head, self.employee])
            db.flush()
            self.root = Department(name="Operations", head_user_id=self.head.id)
            db.add(self.root)
            db.flush()
            self.child = Department(name="Manufacturing", parent_id=self.root.id)
            db.add(self.child)
            db.flush()
            self.head.department_id = self.root.id
            self.employee.department_id = self.child.id
            db.commit()
            self.admin_id = self.admin.id
            self.head_id = self.head.id
            self.employee_id = self.employee.id
            self.root_id = self.root.id
            self.child_id = self.child.id

        self.admin_headers = self._auth_headers(self.admin_id, Role.admin)
        self.employee_headers = self._auth_headers(self.employee_id, Role.employee)

    @staticmethod
    def _auth_headers(user_id: int, role: Role) -> dict[str, str]:
        token = create_access_token(user_id, role.value)
        return {"Authorization": f"Bearer {token}"}

    def test_department_tree_includes_nested_active_employee_counts(self):
        response = self.client.get(
            "/api/v1/departments/tree", headers=self.employee_headers
        )

        self.assertEqual(response.status_code, 200, response.text)
        tree = response.json()
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]["name"], "Operations")
        self.assertEqual(tree[0]["direct_employee_count"], 1)
        self.assertEqual(tree[0]["total_employee_count"], 2)
        self.assertEqual(tree[0]["children"][0]["name"], "Manufacturing")
        self.assertEqual(tree[0]["children"][0]["total_employee_count"], 1)

    def test_admin_can_create_department_with_valid_head_and_audit_entry(self):
        with self.Session() as db:
            spare_head = User(
                employee_code="HEAD-002",
                email="head2@example.com",
                password_hash=hash_password("HeadPass123"),
                full_name="Second Head",
                role=Role.dept_head,
                gender=Gender.other,
                is_active=True,
            )
            db.add(spare_head)
            db.commit()
            spare_head_id = spare_head.id

        response = self.client.post(
            "/api/v1/departments",
            headers=self.admin_headers,
            json={
                "name": "Sustainability",
                "head_user_id": spare_head_id,
                "parent_id": self.root_id,
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["name"], "Sustainability")
        self.assertEqual(body["head"]["id"], spare_head_id)
        with self.Session() as db:
            audit = db.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "department",
                    AuditLog.entity_id == body["id"],
                    AuditLog.action == AuditAction.create,
                )
            ).scalar_one()
            self.assertEqual(audit.actor_user_id, self.admin_id)

    def test_department_rejects_invalid_head_duplicate_head_and_hierarchy_cycle(self):
        invalid_head = self.client.post(
            "/api/v1/departments",
            headers=self.admin_headers,
            json={"name": "Invalid", "head_user_id": self.employee_id},
        )
        duplicate_head = self.client.post(
            "/api/v1/departments",
            headers=self.admin_headers,
            json={"name": "Duplicate", "head_user_id": self.head_id},
        )
        cycle = self.client.patch(
            f"/api/v1/departments/{self.root_id}",
            headers=self.admin_headers,
            json={"parent_id": self.child_id},
        )

        self.assertEqual(invalid_head.status_code, 400, invalid_head.text)
        self.assertEqual(duplicate_head.status_code, 409, duplicate_head.text)
        self.assertEqual(cycle.status_code, 400, cycle.text)

    def test_employee_cannot_mutate_departments_and_delete_soft_deactivates(self):
        forbidden = self.client.patch(
            f"/api/v1/departments/{self.child_id}",
            headers=self.employee_headers,
            json={"name": "Nope"},
        )
        deleted = self.client.delete(
            f"/api/v1/departments/{self.child_id}", headers=self.admin_headers
        )

        self.assertEqual(forbidden.status_code, 403, forbidden.text)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json()["status"], ActiveStatus.inactive.value)
        with self.Session() as db:
            self.assertEqual(
                db.get(Department, self.child_id).status, ActiveStatus.inactive
            )

    def test_admin_can_create_user_with_normalized_identity_and_audit_entry(self):
        response = self.client.post(
            "/api/v1/users",
            headers=self.admin_headers,
            json={
                "employee_code": " EMP-100 ",
                "email": "NEW.USER@EXAMPLE.COM",
                "password": "SecurePass123",
                "full_name": "New User",
                "role": "employee",
                "department_id": self.child_id,
                "gender": "female",
                "job_title": "Engineer",
                "date_joined": dt.date.today().isoformat(),
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["employee_code"], "EMP-100")
        self.assertEqual(body["email"], "new.user@example.com")
        self.assertEqual(body["department_name"], "Manufacturing")
        with self.Session() as db:
            user = db.get(User, body["id"])
            self.assertTrue(verify_password("SecurePass123", user.password_hash))
            audit = db.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "user",
                    AuditLog.entity_id == body["id"],
                    AuditLog.action == AuditAction.create,
                )
            ).scalar_one()
            self.assertNotIn("password_hash", audit.after_json)

    def test_user_create_rejects_duplicate_email_and_employee_code_case_insensitively(
        self,
    ):
        duplicate_email = self.client.post(
            "/api/v1/users",
            headers=self.admin_headers,
            json={
                "employee_code": "EMP-200",
                "email": "EMPLOYEE@EXAMPLE.COM",
                "password": "SecurePass123",
                "full_name": "Duplicate Email",
            },
        )
        duplicate_code = self.client.post(
            "/api/v1/users",
            headers=self.admin_headers,
            json={
                "employee_code": "emp-001",
                "email": "different@example.com",
                "password": "SecurePass123",
                "full_name": "Duplicate Code",
            },
        )

        self.assertEqual(duplicate_email.status_code, 409, duplicate_email.text)
        self.assertEqual(duplicate_code.status_code, 409, duplicate_code.text)

    def test_user_list_supports_search_role_department_and_active_filters(self):
        response = self.client.get(
            "/api/v1/users",
            headers=self.admin_headers,
            params={
                "search": "active employee",
                "role": "employee",
                "department_id": self.child_id,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["id"], self.employee_id)

    def test_admin_can_update_user_reset_password_and_deactivate(self):
        updated = self.client.patch(
            f"/api/v1/users/{self.employee_id}",
            headers=self.admin_headers,
            json={"job_title": "Senior Engineer", "gender": "other"},
        )
        reset = self.client.post(
            f"/api/v1/users/{self.employee_id}/reset-password",
            headers=self.admin_headers,
            json={"new_password": "ResetPass123"},
        )
        deactivated = self.client.delete(
            f"/api/v1/users/{self.employee_id}", headers=self.admin_headers
        )

        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["job_title"], "Senior Engineer")
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(deactivated.status_code, 200, deactivated.text)
        self.assertFalse(deactivated.json()["is_active"])
        with self.Session() as db:
            self.assertTrue(
                verify_password(
                    "ResetPass123", db.get(User, self.employee_id).password_hash
                )
            )

    def test_admin_cannot_deactivate_self_or_an_assigned_department_head(self):
        self_deactivate = self.client.delete(
            f"/api/v1/users/{self.admin_id}", headers=self.admin_headers
        )
        head_deactivate = self.client.delete(
            f"/api/v1/users/{self.head_id}", headers=self.admin_headers
        )

        self.assertEqual(self_deactivate.status_code, 400, self_deactivate.text)
        self.assertEqual(head_deactivate.status_code, 409, head_deactivate.text)


if __name__ == "__main__":
    unittest.main()
