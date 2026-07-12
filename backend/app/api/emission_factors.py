from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.core import User
from app.models.enums import ERPType, Scope, ActiveStatus

from app.models.masterdata import EmissionFactor
from app.schemas.common import Page

router = APIRouter(tags=["Emission Factors"])


# --- SCHEMAS ---


class EmissionFactorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: ERPType
    unit: str
    factor_value: float
    scope: Scope
    version: int
    status: ActiveStatus


# --- ENDPOINTS ---


@router.get("/emission-factors", response_model=Page[EmissionFactorOut])
def list_emission_factors(
    page: int = 1,
    size: int = Query(20, le=100),
    source_type: ERPType | None = None,
    current: User = Depends(
        get_current_user
    ),  # Wait, User is not imported, let's import it or just omit type hint
    db: Session = Depends(get_db),
):
    offset = (page - 1) * size
    query = select(EmissionFactor).order_by(
        EmissionFactor.name.asc(), EmissionFactor.version.desc()
    )

    if source_type is not None:
        query = query.where(EmissionFactor.source_type == source_type)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = db.execute(query.offset(offset).limit(size)).scalars().all()

    return Page[EmissionFactorOut](items=items, total=total)
