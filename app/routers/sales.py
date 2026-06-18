from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from ..database import get_db
from .. import models, schemas
from ..auth import require_roles, get_current_active_user
from ..websocket_manager import manager

router = APIRouter()

staff_only = require_roles(models.UserRole.ADMIN, models.UserRole.VENDEDOR)


def next_sale_number(db: Session) -> int:
    max_num = db.query(func.max(models.Sale.sale_number)).scalar()
    return (max_num or 0) + 1


def next_pending_order_number(db: Session) -> int:
    max_num = db.query(func.max(models.PendingOrder.order_number)).scalar()
    return (max_num or 0) + 1


@router.get("/", response_model=List[schemas.SaleResponse])
async def get_sales(
    response: Response,
    limit: int = 15,
    offset: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    cash_register_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    query = db.query(models.Sale)
    if current_user.role == models.UserRole.VENDEDOR:
        query = query.filter(models.Sale.user_id == current_user.id)
    if cash_register_id:
        query = query.filter(models.Sale.cash_register_id == cash_register_id)
    if date_from:
        query = query.filter(models.Sale.created_at >= date_from + ' 00:00:00')
    if date_to:
        query = query.filter(models.Sale.created_at <= date_to + ' 23:59:59')
    total = query.count()
    response.headers['X-Total-Count'] = str(total)
    return query.order_by(models.Sale.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{sale_id}", response_model=schemas.SaleResponse)
async def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if current_user.role == models.UserRole.VENDEDOR and sale.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sin acceso a esta venta")
    return sale


@router.post("/", response_model=schemas.SaleResponse)
async def create_sale(
    sale_in: schemas.SaleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    register = db.query(models.CashRegister).filter(
        models.CashRegister.id == sale_in.cash_register_id,
        models.CashRegister.status == models.CashRegisterStatus.OPEN
    ).first()
    if not register:
        raise HTTPException(status_code=400, detail="Caja no encontrada o cerrada")

    if not sale_in.items:
        raise HTTPException(status_code=400, detail="La venta debe tener al menos un producto")

    subtotal = 0.0
    sale_items = []

    for item_in in sale_in.items:
        product = db.query(models.Product).filter(
            models.Product.id == item_in.product_id,
            models.Product.is_active == True
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Producto {item_in.product_id} no encontrado")
        if product.is_out_of_stock:
            raise HTTPException(status_code=400, detail=f"{product.name} está fuera de stock")

        item_subtotal = item_in.quantity * item_in.unit_price
        subtotal += item_subtotal
        sale_items.append(models.SaleItem(
            product_id=item_in.product_id,
            product_name=item_in.product_name or product.name,
            quantity=item_in.quantity,
            unit_price=item_in.unit_price,
            subtotal=item_subtotal,
            notes=item_in.notes
        ))

        for assoc in product.raw_materials:
            assoc.raw_material.quantity -= assoc.quantity_per_unit * item_in.quantity

        product.stock_quantity -= item_in.quantity

    total = subtotal - sale_in.discount
    change = None
    if sale_in.payment_method == models.PaymentMethod.CASH and sale_in.amount_received:
        change = sale_in.amount_received - total

    if sale_in.payment_method == models.PaymentMethod.JUNAEB:
        if not sale_in.transaction_code or not sale_in.transaction_code.strip():
            raise HTTPException(status_code=400, detail="El código de transacción JUNAEB es obligatorio")

    notes = sale_in.notes
    if sale_in.payment_method == models.PaymentMethod.JUNAEB and sale_in.transaction_code:
        notes = f"Código JUNAEB: {sale_in.transaction_code.strip()}"

    sale = models.Sale(
        sale_number=next_sale_number(db),
        user_id=current_user.id,
        cash_register_id=sale_in.cash_register_id,
        customer_name=sale_in.customer_name,
        subtotal=subtotal,
        discount=sale_in.discount,
        total=total,
        payment_method=sale_in.payment_method,
        amount_received=sale_in.amount_received,
        change_given=change,
        notes=notes,
        status=models.SaleStatus.COMPLETED,
        items=sale_items
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)

    # Crear pedido pendiente para el flujo de preparacion
    pending_order = models.PendingOrder(
        order_number=next_pending_order_number(db),
        customer_name=sale.customer_name,
        total=sale.total,
        notes=f"Venta #{sale.sale_number} — {current_user.full_name}",
        status=models.PendingOrderStatus.WAITING,
        items=[
            models.PendingOrderItem(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.subtotal,
            )
            for item in sale.items
        ]
    )
    db.add(pending_order)
    db.commit()
    db.refresh(pending_order)

    await manager.broadcast({
        "type": "sale_created",
        "sale": {
            "id": sale.id,
            "sale_number": sale.sale_number,
            "total": sale.total,
            "seller": current_user.full_name
        }
    })
    await manager.broadcast({
        "type": "pending_order_created",
        "order": {
            "id": pending_order.id,
            "order_number": pending_order.order_number,
            "customer_name": pending_order.customer_name,
            "total": pending_order.total,
            "items_count": len(pending_order.items),
            "notes": pending_order.notes,
        }
    })
    return sale


@router.patch("/{sale_id}/cancel")
async def cancel_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.UserRole.ADMIN))
):
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if sale.status == models.SaleStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="La venta ya está cancelada")

    sale.status = models.SaleStatus.CANCELLED
    db.commit()
    return {"message": "Venta cancelada"}
