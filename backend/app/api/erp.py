import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_esg
from app.db.session import get_db
from app.models.core import Department, User
from app.models.enums import ActiveStatus, AuditAction, ERPType
from app.models.environment import ERPOperation, ERPOperationLine, CarbonTransaction
from app.models.masterdata import EmissionFactor
from app.schemas.common import Msg, Page
from app.services.audit import log_action, snapshot
from app.services.carbon_accounting import calculate_and_create_carbon_cost
from app.services.org_settings import get_org_settings

router = APIRouter(tags=["ERP"])


# --- SCHEMAS ---

class ERPOperationLineCreate(BaseModel):
    resource: str = Field(..., max_length=120)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., max_length=20)


class ERPOperationLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource: str
    quantity: float
    unit: str


class ERPOperationCreate(BaseModel):
    op_type: ERPType
    department_id: int
    op_date: dt.date
    reference_no: str = Field(..., max_length=40)
    amount_inr: float | None = Field(None, ge=0)
    notes: str | None = None
    lines: list[ERPOperationLineCreate] = Field(..., min_items=1)


class ERPOperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    op_type: ERPType
    department_id: int
    department_name: str | None = None
    op_date: dt.date
    reference_no: str
    amount_inr: float | None
    notes: str | None
    created_at: dt.datetime
    lines: list[ERPOperationLineOut]


# --- ENDPOINTS ---

@router.post("/erp/operations", response_model=ERPOperationOut)
def create_erp_operation(
    payload: ERPOperationCreate,
    current: User = Depends(require_esg),
    db: Session = Depends(get_db),
):
    dept = db.get(Department, payload.department_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    if dept.status != ActiveStatus.active:
        raise HTTPException(status_code=400, detail="Cannot assign operation to an inactive department")

    # Check reference number uniqueness
    existing_ref = db.execute(
        select(ERPOperation).where(ERPOperation.reference_no == payload.reference_no)
    ).scalar_one_or_none()
    if existing_ref:
        raise HTTPException(status_code=409, detail="Operation reference number already exists")

    op = ERPOperation(
        op_type=payload.op_type,
        department_id=payload.department_id,
        op_date=payload.op_date,
        reference_no=payload.reference_no,
        amount_inr=payload.amount_inr,
        notes=payload.notes,
        created_by=current.id,
    )
    db.add(op)
    db.flush()

    for line_data in payload.lines:
        line = ERPOperationLine(
            operation_id=op.id,
            resource=line_data.resource,
            quantity=line_data.quantity,
            unit=line_data.unit,
        )
        db.add(line)
        db.flush()

        # If auto emission is enabled, trigger carbon calculation
        settings = get_org_settings(db)
        if settings.auto_emission_calc:
            # Find emission factor
            factor = db.execute(
                select(EmissionFactor).where(
                    EmissionFactor.status == ActiveStatus.active,
                    EmissionFactor.source_type == payload.op_type,
                    func.lower(EmissionFactor.name).like(f"%{line_data.resource.lower()}%")
                ).limit(1)
            ).scalar_one_or_none()

            # Fallback to any active factor for the source type if name match fails
            if not factor:
                factor = db.execute(
                    select(EmissionFactor).where(
                        EmissionFactor.status == ActiveStatus.active,
                        EmissionFactor.source_type == payload.op_type
                    ).limit(1)
                ).scalar_one_or_none()

            if factor:
                co2e_kg = line.quantity * float(factor.factor_value)
                tx = CarbonTransaction(
                    erp_line_id=line.id,
                    department_id=payload.department_id,
                    activity_date=payload.op_date,
                    description=f"ERP Auto: {payload.op_type.value.capitalize()} - {line_data.resource}",
                    quantity=line.quantity,
                    unit=line.unit,
                    emission_factor_id=factor.id,
                    factor_value_snapshot=factor.factor_value,
                    factor_version_snapshot=factor.version,
                    co2e_kg=co2e_kg,
                    scope=factor.scope,
                    is_auto=True,
                    created_by=current.id,
                )
                db.add(tx)
                db.flush()

                # Trigger cost calculation
                calculate_and_create_carbon_cost(db, tx)
                db.flush()

    log_action(
        db,
        current.id,
        AuditAction.create,
        "ERPOperation",
        op.id,
        op.reference_no,
        after=snapshot(op, ["reference_no", "amount_inr", "op_type"]),
    )

    db.commit()
    db.refresh(op)

    out = ERPOperationOut.model_validate(op)
    out.department_name = dept.name
    return out


@router.get("/erp/operations", response_model=Page[ERPOperationOut])
def list_erp_operations(
    page: int = 1,
    size: int = Query(20, le=100),
    department_id: int | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * size
    query = select(ERPOperation).options(
        selectinload(ERPOperation.lines)
    ).order_by(ERPOperation.op_date.desc(), ERPOperation.id.desc())

    if department_id is not None:
        query = query.where(ERPOperation.department_id == department_id)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = db.execute(query.offset(offset).limit(size)).scalars().all()

    dept_names = {d.id: d.name for d in db.execute(select(Department)).scalars().all()}

    out_items = []
    for op in items:
        out = ERPOperationOut.model_validate(op)
        out.department_name = dept_names.get(op.department_id)
        out_items.append(out)

    return Page[ERPOperationOut](items=out_items, total=total)
