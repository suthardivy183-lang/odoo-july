from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_esg
from app.db.session import get_db
from app.models.core import User
from app.models.enums import ActiveStatus, AuditAction, CategoryType
from app.models.gamification import Challenge
from app.models.masterdata import Category
from app.models.social import CSRActivity
from app.schemas.categories import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.common import Msg, Page
from app.services.audit import log_action, snapshot

router = APIRouter(tags=["Categories"])

AUDIT_FIELDS = ["name", "type", "status"]


@router.get("/categories", response_model=Page[CategoryOut])
def list_categories(
    type: CategoryType | None = None,
    status: ActiveStatus | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = Query(20, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Category)
    if type is not None:
        stmt = stmt.where(Category.type == type)
    if status is not None:
        stmt = stmt.where(Category.status == status)
    if q:
        stmt = stmt.where(Category.name.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = (
        db.execute(
            stmt.order_by(Category.created_at.desc()).offset((page - 1) * size).limit(size)
        )
        .scalars()
        .all()
    )
    return Page[CategoryOut](items=items, total=total)


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    dup = db.execute(
        select(Category).where(Category.name == payload.name, Category.type == payload.type)
    ).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(status_code=409, detail="A category with this name and type already exists")
    category = Category(name=payload.name, type=payload.type, status=payload.status)
    db.add(category)
    db.flush()
    log_action(
        db, current.id, AuditAction.create, "category", category.id,
        entity_label=category.name, after=snapshot(category, AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    before = snapshot(category, AUDIT_FIELDS)
    if payload.name is not None and payload.name != category.name:
        dup = db.execute(
            select(Category).where(
                Category.name == payload.name,
                Category.type == category.type,
                Category.id != category.id,
            )
        ).scalar_one_or_none()
        if dup is not None:
            raise HTTPException(status_code=409, detail="A category with this name and type already exists")
        category.name = payload.name
    if payload.status is not None:
        category.status = payload.status
    log_action(
        db, current.id, AuditAction.update, "category", category.id,
        entity_label=category.name, before=before, after=snapshot(category, AUDIT_FIELDS),
    )
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", response_model=Msg)
def delete_category(
    category_id: int,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    used_by_csr = db.execute(
        select(func.count(CSRActivity.id)).where(CSRActivity.category_id == category.id)
    ).scalar_one()
    used_by_challenge = db.execute(
        select(func.count(Challenge.id)).where(Challenge.category_id == category.id)
    ).scalar_one()
    if used_by_csr or used_by_challenge:
        raise HTTPException(
            status_code=409,
            detail="Category is in use by activities or challenges; mark it inactive instead",
        )
    before = snapshot(category, AUDIT_FIELDS)
    db.delete(category)
    log_action(
        db, current.id, AuditAction.delete, "category", category_id,
        entity_label=category.name, before=before,
    )
    db.commit()
    return Msg(detail="Category deleted")
