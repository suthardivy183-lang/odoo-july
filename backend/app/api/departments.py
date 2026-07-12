from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.core import Department, User
from app.models.enums import ActiveStatus, AuditAction, Role
from app.schemas.common import Page
from app.schemas.departments import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentTreeOut,
    DepartmentUpdate,
)
from app.services.audit import log_action, snapshot
from app.services.org import dept_employee_counts, would_create_cycle

router = APIRouter(tags=["Departments"])

DEPARTMENT_FIELDS = ["id", "name", "head_user_id", "parent_id", "status"]


def _get_department(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


def _validate_unique_name(
    db: Session, name: str, *, exclude_department_id: int | None = None
) -> None:
    query = select(Department.id).where(func.lower(Department.name) == name.lower())
    if exclude_department_id is not None:
        query = query.where(Department.id != exclude_department_id)
    if db.execute(query).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="A department with this name already exists"
        )


def _validate_parent(
    db: Session, parent_id: int | None, *, department_id: int | None = None
) -> None:
    if parent_id is None:
        return
    parent = db.get(Department, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent department not found")
    if department_id is not None and would_create_cycle(db, department_id, parent_id):
        raise HTTPException(
            status_code=400, detail="Parent assignment would create a hierarchy cycle"
        )


def _validate_head(
    db: Session, head_user_id: int | None, *, department_id: int | None = None
) -> None:
    if head_user_id is None:
        return
    head = db.get(User, head_user_id)
    if head is None:
        raise HTTPException(status_code=404, detail="Department head user not found")
    if not head.is_active or head.role != Role.dept_head:
        raise HTTPException(
            status_code=400, detail="Department head must be an active dept_head user"
        )
    query = select(Department.id).where(Department.head_user_id == head_user_id)
    if department_id is not None:
        query = query.where(Department.id != department_id)
    if db.execute(query).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="This user already heads another department"
        )


def _department_out(
    department: Department, counts: dict[int, dict[str, int]]
) -> DepartmentOut:
    count = counts.get(department.id, {"direct": 0, "total": 0})
    return DepartmentOut(
        id=department.id,
        name=department.name,
        head_user_id=department.head_user_id,
        head=department.head,
        parent_id=department.parent_id,
        status=department.status,
        direct_employee_count=count["direct"],
        total_employee_count=count["total"],
        created_at=department.created_at,
        updated_at=department.updated_at,
    )


@router.get("/departments", response_model=Page[DepartmentOut])
def list_departments(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    department_status: ActiveStatus | None = Query(None, alias="status"),
    parent_id: int | None = None,
    _current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = []
    if search and search.strip():
        filters.append(Department.name.ilike(f"%{search.strip()}%"))
    if department_status is not None:
        filters.append(Department.status == department_status)
    if parent_id is not None:
        filters.append(Department.parent_id == parent_id)
    total = db.execute(select(func.count(Department.id)).where(*filters)).scalar_one()
    departments = (
        db.execute(
            select(Department)
            .options(selectinload(Department.head))
            .where(*filters)
            .order_by(Department.name.asc(), Department.id.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    counts = dept_employee_counts(db)
    return Page(
        items=[_department_out(item, counts) for item in departments], total=total
    )


@router.get("/departments/tree", response_model=list[DepartmentTreeOut])
def department_tree(
    include_inactive: bool = False,
    _current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        select(Department)
        .options(selectinload(Department.head))
        .order_by(Department.name)
    )
    if not include_inactive:
        query = query.where(Department.status == ActiveStatus.active)
    departments = db.execute(query).scalars().all()
    counts = dept_employee_counts(db)
    included_ids = {department.id for department in departments}
    by_parent: dict[int | None, list[Department]] = {}
    for department in departments:
        parent_key = (
            department.parent_id if department.parent_id in included_ids else None
        )
        by_parent.setdefault(parent_key, []).append(department)

    def build(parent_id: int | None) -> list[DepartmentTreeOut]:
        nodes: list[DepartmentTreeOut] = []
        for department in by_parent.get(parent_id, []):
            base = _department_out(department, counts)
            nodes.append(
                DepartmentTreeOut(**base.model_dump(), children=build(department.id))
            )
        return nodes

    return build(None)


@router.get("/departments/{department_id}", response_model=DepartmentOut)
def get_department(
    department_id: int,
    _current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _department_out(_get_department(db, department_id), dept_employee_counts(db))


@router.post(
    "/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED
)
def create_department(
    payload: DepartmentCreate,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _validate_unique_name(db, payload.name)
    _validate_parent(db, payload.parent_id)
    _validate_head(db, payload.head_user_id)
    department = Department(**payload.model_dump())
    db.add(department)
    db.flush()
    log_action(
        db,
        current.id,
        AuditAction.create,
        "department",
        department.id,
        entity_label=department.name,
        after=snapshot(department, DEPARTMENT_FIELDS),
    )
    db.commit()
    db.refresh(department)
    return _department_out(department, dept_employee_counts(db))


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    department = _get_department(db, department_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No department changes supplied")
    if "name" in changes:
        if changes["name"] is None:
            raise HTTPException(
                status_code=400, detail="Department name cannot be null"
            )
        _validate_unique_name(db, changes["name"], exclude_department_id=department.id)
    if "parent_id" in changes:
        _validate_parent(db, changes["parent_id"], department_id=department.id)
    if "head_user_id" in changes:
        _validate_head(db, changes["head_user_id"], department_id=department.id)
    if changes.get("status", department.status) is None:
        raise HTTPException(status_code=400, detail="Department status cannot be null")
    before = snapshot(department, DEPARTMENT_FIELDS)
    for field, value in changes.items():
        setattr(department, field, value)
    log_action(
        db,
        current.id,
        AuditAction.update,
        "department",
        department.id,
        entity_label=department.name,
        before=before,
        after=snapshot(department, DEPARTMENT_FIELDS),
    )
    db.commit()
    db.refresh(department)
    return _department_out(department, dept_employee_counts(db))


@router.delete("/departments/{department_id}", response_model=DepartmentOut)
def deactivate_department(
    department_id: int,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    department = _get_department(db, department_id)
    if department.status == ActiveStatus.inactive:
        raise HTTPException(status_code=409, detail="Department is already inactive")
    before = snapshot(department, DEPARTMENT_FIELDS)
    department.status = ActiveStatus.inactive
    log_action(
        db,
        current.id,
        AuditAction.delete,
        "department",
        department.id,
        entity_label=department.name,
        before=before,
        after=snapshot(department, DEPARTMENT_FIELDS),
    )
    db.commit()
    db.refresh(department)
    return _department_out(department, dept_employee_counts(db))
