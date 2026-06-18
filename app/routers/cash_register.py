from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from ..utils import now_santiago
from ..database import get_db
from .. import models, schemas
from ..auth import require_roles, get_current_active_user
from ..websocket_manager import manager

router = APIRouter()

staff_only = require_roles(models.UserRole.ADMIN, models.UserRole.VENDEDOR)


@router.get("/", response_model=List[schemas.CashRegisterResponse])
async def get_cash_registers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    query = db.query(models.CashRegister)
    if current_user.role == models.UserRole.VENDEDOR:
        query = query.filter(models.CashRegister.user_id == current_user.id)
    return query.order_by(models.CashRegister.opened_at.desc()).all()


@router.get("/current", response_model=schemas.CashRegisterResponse)
async def get_current_register(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    register = db.query(models.CashRegister).filter(
        models.CashRegister.user_id == current_user.id,
        models.CashRegister.status == models.CashRegisterStatus.OPEN
    ).first()
    if not register:
        raise HTTPException(status_code=404, detail="No hay caja abierta")
    return register


@router.post("/open", response_model=schemas.CashRegisterResponse)
async def open_cash_register(
    register_in: schemas.CashRegisterOpen,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    existing = db.query(models.CashRegister).filter(
        models.CashRegister.user_id == current_user.id,
        models.CashRegister.status == models.CashRegisterStatus.OPEN
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya tienes una caja abierta")

    register = models.CashRegister(
        user_id=current_user.id,
        opening_amount=register_in.opening_amount,
        notes=register_in.notes,
        status=models.CashRegisterStatus.OPEN
    )
    db.add(register)
    db.commit()
    db.refresh(register)

    await manager.broadcast({
        "type": "cash_register_opened",
        "register": {"id": register.id, "user": current_user.full_name}
    })
    return register


@router.post("/{register_id}/close", response_model=schemas.CashRegisterResponse)
async def close_cash_register(
    register_id: int,
    close_in: schemas.CashRegisterClose,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    register = db.query(models.CashRegister).filter(
        models.CashRegister.id == register_id
    ).first()
    if not register:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    if register.status == models.CashRegisterStatus.CLOSED:
        raise HTTPException(status_code=400, detail="La caja ya está cerrada")
    if current_user.role == models.UserRole.VENDEDOR and register.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para cerrar esta caja")

    cash_sales = db.query(func.sum(models.Sale.total)).filter(
        models.Sale.cash_register_id == register_id,
        models.Sale.payment_method == models.PaymentMethod.CASH,
        models.Sale.status == models.SaleStatus.COMPLETED
    ).scalar() or 0

    expected = register.opening_amount + cash_sales
    difference = close_in.closing_amount - expected

    register.closing_amount = close_in.closing_amount
    register.expected_amount = expected
    register.difference = difference
    register.status = models.CashRegisterStatus.CLOSED
    register.closed_at = now_santiago()
    if close_in.notes:
        register.notes = close_in.notes

    db.commit()
    db.refresh(register)

    await manager.broadcast({
        "type": "cash_register_closed",
        "register": {
            "id": register.id,
            "user": current_user.full_name,
            "difference": difference
        }
    })
    return register
