"""Department hierarchy helpers and approval-scope rules."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Department, User
from app.models.enums import Role


def _children_map(db: Session) -> dict[int | None, list[Department]]:
    depts = db.execute(select(Department)).scalars().all()
    by_parent: dict[int | None, list[Department]] = {}
    for d in depts:
        by_parent.setdefault(d.parent_id, []).append(d)
    return by_parent


def descendant_dept_ids(db: Session, root_id: int) -> set[int]:
    """root_id plus every nested child department id."""
    by_parent = _children_map(db)
    result: set[int] = set()
    stack = [root_id]
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(d.id for d in by_parent.get(current, []))
    return result


def managed_dept_ids(db: Session, user: User) -> set[int]:
    """Departments the user heads, including all descendants."""
    headed = (
        db.execute(select(Department.id).where(Department.head_user_id == user.id))
        .scalars()
        .all()
    )
    result: set[int] = set()
    for dept_id in headed:
        result |= descendant_dept_ids(db, dept_id)
    return result


def ancestor_chain(db: Session, dept_id: int) -> list[Department]:
    """Department, then its parent, grandparent, ... (cycle-safe)."""
    chain: list[Department] = []
    seen: set[int] = set()
    current = db.get(Department, dept_id)
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append(current)
        current = db.get(Department, current.parent_id) if current.parent_id else None
    return chain


def responsible_head(db: Session, dept_id: int | None) -> User | None:
    """Nearest head walking up from the department (for notifications/approvals)."""
    if dept_id is None:
        return None
    for dept in ancestor_chain(db, dept_id):
        if dept.head_user_id:
            head = db.get(User, dept.head_user_id)
            if head and head.is_active:
                return head
    return None


def can_decide_for(db: Session, actor: User, employee: User) -> bool:
    """Approval-scope rule for CSR/challenge decisions.

    - Admin can decide anything (including a head's own submissions).
    - Nobody else may decide their own submission.
    - A dept head decides for employees in departments they head (incl. descendants,
      via any ancestor department they head).
    """
    if actor.role == Role.admin:
        return True
    if actor.id == employee.id:
        return False
    if actor.role != Role.dept_head:
        return False
    if employee.department_id is None:
        return False
    return employee.department_id in managed_dept_ids(db, actor)


def would_create_cycle(db: Session, dept_id: int, new_parent_id: int | None) -> bool:
    """True if setting new_parent_id on dept_id would create a hierarchy cycle."""
    if new_parent_id is None:
        return False
    if new_parent_id == dept_id:
        return True
    return dept_id in {d.id for d in ancestor_chain(db, new_parent_id)}


def dept_employee_counts(db: Session) -> dict[int, dict[str, int]]:
    """{dept_id: {"direct": n, "total": n(incl. descendants)}} for active users."""
    users = db.execute(select(User.department_id).where(User.is_active.is_(True))).all()
    direct: dict[int, int] = {}
    for (dept_id,) in users:
        if dept_id is not None:
            direct[dept_id] = direct.get(dept_id, 0) + 1
    depts = db.execute(select(Department.id)).scalars().all()
    result: dict[int, dict[str, int]] = {}
    for dept_id in depts:
        total = sum(direct.get(d, 0) for d in descendant_dept_ids(db, dept_id))
        result[dept_id] = {"direct": direct.get(dept_id, 0), "total": total}
    return result
