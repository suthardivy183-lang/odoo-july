from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.core import Department, User
from app.models.enums import ActiveStatus, AuditAction, Gender, Role
from app.schemas.common import Msg, Page
from app.schemas.users import ManagedUserOut, PasswordReset, UserCreate, UserUpdate
from app.services.audit import log_action, snapshot

router = APIRouter(tags=["Users"])

USER_FIELDS = [
    "id",
    "employee_code",
    "email",
    "full_name",
    "role",
    "department_id",
    "gender",
    "job_title",
    "date_joined",
    "is_active",
]


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _user_out(user: User) -> ManagedUserOut:
    out = ManagedUserOut.model_validate(user)
    out.department_name = user.department.name if user.department else None
    return out


def _validate_department(db: Session, department_id: int | None) -> None:
    if department_id is None:
        return
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    if department.status != ActiveStatus.active:
        raise HTTPException(
            status_code=400, detail="User cannot be assigned to an inactive department"
        )


def _validate_identity_unique(
    db: Session,
    *,
    email: str | None = None,
    employee_code: str | None = None,
    exclude_user_id: int | None = None,
) -> None:
    if email is not None:
        query = select(User.id).where(func.lower(User.email) == email.lower())
        if exclude_user_id is not None:
            query = query.where(User.id != exclude_user_id)
        if db.execute(query).scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409, detail="A user with this email already exists"
            )
    if employee_code is not None:
        query = select(User.id).where(
            func.lower(User.employee_code) == employee_code.lower()
        )
        if exclude_user_id is not None:
            query = query.where(User.id != exclude_user_id)
        if db.execute(query).scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409, detail="A user with this employee code already exists"
            )


def _headed_department(db: Session, user_id: int) -> Department | None:
    return db.execute(
        select(Department).where(Department.head_user_id == user_id).limit(1)
    ).scalar_one_or_none()


def _validate_head_role_and_activity(
    db: Session,
    user: User,
    *,
    new_role: Role | None = None,
    new_active: bool | None = None,
) -> None:
    headed = _headed_department(db, user.id)
    if headed is None:
        return
    if new_role is not None and new_role != Role.dept_head:
        raise HTTPException(
            status_code=409,
            detail=f"Reassign the head of {headed.name} before changing this user's role",
        )
    if new_active is False:
        raise HTTPException(
            status_code=409,
            detail=f"Reassign the head of {headed.name} before deactivating this user",
        )


@router.get("/users", response_model=Page[ManagedUserOut])
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    role: Role | None = None,
    department_id: int | None = None,
    gender: Gender | None = None,
    is_active: bool | None = None,
    _current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    filters = []
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                User.employee_code.ilike(pattern),
            )
        )
    if role is not None:
        filters.append(User.role == role)
    if department_id is not None:
        filters.append(User.department_id == department_id)
    if gender is not None:
        filters.append(User.gender == gender)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    total = db.execute(select(func.count(User.id)).where(*filters)).scalar_one()
    users = (
        db.execute(
            select(User)
            .options(selectinload(User.department))
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return Page(items=[_user_out(user) for user in users], total=total)


@router.get("/users/{user_id}", response_model=ManagedUserOut)
def get_user(
    user_id: int,
    _current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _user_out(_get_user(db, user_id))


@router.post(
    "/users", response_model=ManagedUserOut, status_code=status.HTTP_201_CREATED
)
def create_user(
    payload: UserCreate,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    email = str(payload.email).lower()
    employee_code = payload.employee_code.strip()
    _validate_identity_unique(db, email=email, employee_code=employee_code)
    _validate_department(db, payload.department_id)
    values = payload.model_dump(exclude={"password"})
    values.update(
        email=email,
        employee_code=employee_code,
        password_hash=hash_password(payload.password),
    )
    user = User(**values)
    db.add(user)
    db.flush()
    log_action(
        db,
        current.id,
        AuditAction.create,
        "user",
        user.id,
        entity_label=user.full_name,
        after=snapshot(user, USER_FIELDS),
    )
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.patch("/users/{user_id}", response_model=ManagedUserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No user changes supplied")
    non_nullable = {
        "employee_code",
        "email",
        "full_name",
        "role",
        "gender",
        "is_active",
    }
    if any(changes.get(field) is None for field in non_nullable & changes.keys()):
        raise HTTPException(
            status_code=400, detail="A required user field cannot be null"
        )
    if "email" in changes:
        changes["email"] = str(changes["email"]).lower()
    if "employee_code" in changes:
        changes["employee_code"] = changes["employee_code"].strip()
    _validate_identity_unique(
        db,
        email=changes.get("email"),
        employee_code=changes.get("employee_code"),
        exclude_user_id=user.id,
    )
    if "department_id" in changes:
        _validate_department(db, changes["department_id"])
    _validate_head_role_and_activity(
        db,
        user,
        new_role=changes.get("role"),
        new_active=changes.get("is_active"),
    )
    if user.id == current.id and changes.get("is_active") is False:
        raise HTTPException(
            status_code=400, detail="You cannot deactivate your own account"
        )
    before = snapshot(user, USER_FIELDS)
    for field, value in changes.items():
        setattr(user, field, value)
    log_action(
        db,
        current.id,
        AuditAction.update,
        "user",
        user.id,
        entity_label=user.full_name,
        before=before,
        after=snapshot(user, USER_FIELDS),
    )
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.post("/users/{user_id}/reset-password", response_model=Msg)
def reset_user_password(
    user_id: int,
    payload: PasswordReset,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    log_action(
        db,
        current.id,
        AuditAction.update,
        "user",
        user.id,
        entity_label=user.full_name,
        before={"password_reset": False},
        after={"password_reset": True},
    )
    db.commit()
    return Msg(detail="Password reset")


@router.delete("/users/{user_id}", response_model=ManagedUserOut)
def deactivate_user(
    user_id: int,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_id)
    if user.id == current.id:
        raise HTTPException(
            status_code=400, detail="You cannot deactivate your own account"
        )
    if not user.is_active:
        raise HTTPException(status_code=409, detail="User is already inactive")
    _validate_head_role_and_activity(db, user, new_active=False)
    before = snapshot(user, USER_FIELDS)
    user.is_active = False
    log_action(
        db,
        current.id,
        AuditAction.delete,
        "user",
        user.id,
        entity_label=user.full_name,
        before=before,
        after=snapshot(user, USER_FIELDS),
    )
    db.commit()
    db.refresh(user)
    return _user_out(user)
