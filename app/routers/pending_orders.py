from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import List
from datetime import timedelta
from ..database import get_db
from .. import models, schemas
from ..auth import require_roles
from ..websocket_manager import manager
from ..utils import now_santiago

router = APIRouter()

staff_only = require_roles(models.UserRole.ADMIN, models.UserRole.VENDEDOR)


def next_order_number(db: Session) -> int:
    max_num = db.query(func.max(models.PendingOrder.order_number)).scalar()
    return (max_num or 0) + 1


@router.post("/", response_model=schemas.PendingOrderResponse)
async def create_pending_order(
    order_in: schemas.PendingOrderCreate,
    db: Session = Depends(get_db)
):
    if not order_in.items:
        raise HTTPException(status_code=400, detail="El pedido debe tener al menos un producto")
    if not order_in.customer_name or not order_in.customer_name.strip():
        raise HTTPException(status_code=400, detail="El nombre del cliente es obligatorio")

    total = sum(i.quantity * i.unit_price for i in order_in.items)

    order = models.PendingOrder(
        order_number=next_order_number(db),
        customer_name=order_in.customer_name.strip(),
        total=total,
        notes=order_in.notes,
        status=models.PendingOrderStatus.PENDING_PAYMENT,
        items=[
            models.PendingOrderItem(
                product_id=i.product_id,
                product_name=i.product_name,
                quantity=i.quantity,
                unit_price=i.unit_price,
                subtotal=i.quantity * i.unit_price,
            )
            for i in order_in.items
        ]
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    await manager.broadcast({
        "type": "pending_order_created",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "customer_name": order.customer_name,
            "total": order.total,
            "status": order.status.value,
            "items_count": len(order.items),
        }
    })
    return order


@router.get("/", response_model=List[schemas.PendingOrderResponse])
async def get_pending_orders(
    status: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    attended_cutoff = now_santiago() - timedelta(hours=3)
    cancelled_cutoff = now_santiago() - timedelta(hours=1)
    query = db.query(models.PendingOrder).filter(
        or_(
            models.PendingOrder.status.notin_([
                models.PendingOrderStatus.ATTENDED,
                models.PendingOrderStatus.CANCELLED,
            ]),
            and_(
                models.PendingOrder.status == models.PendingOrderStatus.ATTENDED,
                models.PendingOrder.attended_at >= attended_cutoff
            ),
            and_(
                models.PendingOrder.status == models.PendingOrderStatus.CANCELLED,
                models.PendingOrder.cancelled_at >= cancelled_cutoff
            ),
        )
    )
    if status:
        query = query.filter(models.PendingOrder.status == status)
    return query.order_by(models.PendingOrder.created_at.asc()).all()


@router.patch("/{order_id}/status", response_model=schemas.PendingOrderResponse)
async def update_order_status(
    order_id: int,
    update: schemas.PendingOrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    order = db.query(models.PendingOrder).filter(models.PendingOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    order.status = update.status
    if update.status == models.PendingOrderStatus.ATTENDED:
        order.attended_at = now_santiago()
    elif update.status == models.PendingOrderStatus.CANCELLED:
        order.cancelled_at = now_santiago()
    db.commit()
    db.refresh(order)

    await manager.broadcast({
        "type": "pending_order_updated",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status.value,
            "notes": order.notes,
        }
    })
    return order


@router.delete("/{order_id}")
async def delete_pending_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    order = db.query(models.PendingOrder).filter(
        models.PendingOrder.id == order_id,
        models.PendingOrder.status == models.PendingOrderStatus.PENDING_PAYMENT
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado o ya procesado")
    db.delete(order)
    db.commit()
    await manager.broadcast({
        "type": "pending_order_deleted",
        "order": {"id": order_id}
    })
    return {"message": "Pedido cancelado"}


@router.post("/{order_id}/process-payment", response_model=schemas.PendingOrderResponse)
async def process_payment(
    order_id: int,
    payment_in: schemas.PendingOrderPayment,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    order = db.query(models.PendingOrder).filter(
        models.PendingOrder.id == order_id,
        models.PendingOrder.status == models.PendingOrderStatus.PENDING_PAYMENT
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado o ya procesado")

    register = db.query(models.CashRegister).filter(
        models.CashRegister.user_id == current_user.id,
        models.CashRegister.status == models.CashRegisterStatus.OPEN
    ).first()
    if not register:
        raise HTTPException(status_code=400, detail="No tienes una caja abierta. Abre la caja antes de procesar pagos.")

    change = None
    if payment_in.payment_method == models.PaymentMethod.CASH:
        if not payment_in.amount_received or payment_in.amount_received < order.total:
            raise HTTPException(status_code=400, detail="Monto recibido insuficiente")
        change = payment_in.amount_received - order.total

    if payment_in.payment_method == models.PaymentMethod.JUNAEB:
        if not payment_in.transaction_code or not payment_in.transaction_code.strip():
            raise HTTPException(status_code=400, detail="El código de transacción JUNAEB es obligatorio")

    sale_notes = None
    if payment_in.payment_method == models.PaymentMethod.JUNAEB and payment_in.transaction_code:
        sale_notes = f"Código JUNAEB: {payment_in.transaction_code.strip()}"

    max_sale = db.query(func.max(models.Sale.sale_number)).scalar()
    sale_number = (max_sale or 0) + 1

    sale = models.Sale(
        sale_number=sale_number,
        user_id=current_user.id,
        cash_register_id=register.id,
        customer_name=order.customer_name,
        subtotal=order.total,
        discount=0,
        total=order.total,
        payment_method=payment_in.payment_method,
        amount_received=payment_in.amount_received,
        change_given=change,
        notes=sale_notes,
        status=models.SaleStatus.COMPLETED,
        items=[
            models.SaleItem(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.subtotal,
            )
            for item in order.items
        ]
    )
    db.add(sale)

    payment_labels = {
        models.PaymentMethod.CASH: "Efectivo",
        models.PaymentMethod.CARD: "Tarjeta",
        models.PaymentMethod.TRANSFER: "Transferencia",
        models.PaymentMethod.JUNAEB: "JUNAEB",
    }

    order.status = models.PendingOrderStatus.WAITING
    order.notes = f"Pagado: {payment_labels[payment_in.payment_method]} — Venta #{sale_number}"

    for item in order.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if product:
            for assoc in product.raw_materials:
                assoc.raw_material.quantity -= assoc.quantity_per_unit * item.quantity
            product.stock_quantity -= item.quantity

    db.commit()
    db.refresh(order)
    db.refresh(sale)

    await manager.broadcast({
        "type": "sale_created",
        "sale": {
            "id": sale.id,
            "sale_number": sale.sale_number,
            "total": sale.total,
            "seller": current_user.full_name,
        }
    })
    await manager.broadcast({
        "type": "pending_order_updated",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status.value,
            "notes": order.notes,
        }
    })
    return order
