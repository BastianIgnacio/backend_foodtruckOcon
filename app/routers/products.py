from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from .. import models, schemas
from ..auth import get_current_active_user, require_roles
from ..websocket_manager import manager

router = APIRouter()

staff_only = require_roles(models.UserRole.ADMIN, models.UserRole.VENDEDOR)


@router.get("/public", response_model=List[schemas.ProductResponse])
async def get_public_products(
    category: Optional[str] = None,
    carousel_only: bool = False,
    carousel2_only: bool = False,
    carousel3_only: bool = False,
    db: Session = Depends(get_db)
):
    active_cats = db.query(models.Category.name).filter(models.Category.is_active == True)

    query = db.query(models.Product).filter(
        models.Product.is_active == True,
        models.Product.is_out_of_stock == False,
        models.Product.category.in_(active_cats)
    )
    if category:
        query = query.filter(models.Product.category == category)
    if carousel_only:
        query = query.filter(models.Product.show_in_carousel == True)
    if carousel2_only:
        query = query.filter(models.Product.show_in_carousel2 == True)
    if carousel3_only:
        query = query.filter(models.Product.show_in_carousel3 == True)
    return query.all()


@router.get("/", response_model=List[schemas.ProductResponse])
async def get_products(
    category: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    query = db.query(models.Product)
    if active_only:
        query = query.filter(models.Product.is_active == True)
    if category:
        query = query.filter(models.Product.category == category)
    return query.all()


@router.get("/{product_id}", response_model=schemas.ProductResponse)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


@router.post("/", response_model=schemas.ProductResponse)
async def create_product(
    product_in: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    product = models.Product(**product_in.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    await manager.broadcast({
        "type": "product_created",
        "product": {"id": product.id, "name": product.name, "price": product.price}
    })
    return product


@router.put("/{product_id}", response_model=schemas.ProductResponse)
async def update_product(
    product_id: int,
    product_in: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    for field, value in product_in.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    await manager.broadcast({
        "type": "product_updated",
        "product": {"id": product.id, "name": product.name, "stock_quantity": product.stock_quantity}
    })
    return product


@router.patch("/{product_id}/toggle-stock", response_model=schemas.ProductResponse)
async def toggle_out_of_stock(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    product.is_out_of_stock = not product.is_out_of_stock
    db.commit()
    db.refresh(product)
    await manager.broadcast({
        "type": "product_stock_changed",
        "product": {
            "id": product.id,
            "name": product.name,
            "is_out_of_stock": product.is_out_of_stock
        }
    })
    return product


@router.patch("/{product_id}/toggle-carousel", response_model=schemas.ProductResponse)
async def toggle_carousel(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.UserRole.ADMIN))
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product.show_in_carousel = not product.show_in_carousel
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}/toggle-carousel2", response_model=schemas.ProductResponse)
async def toggle_carousel2(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.UserRole.ADMIN))
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product.show_in_carousel2 = not product.show_in_carousel2
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}/toggle-carousel3", response_model=schemas.ProductResponse)
async def toggle_carousel3(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.UserRole.ADMIN))
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product.show_in_carousel3 = not product.show_in_carousel3
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.UserRole.ADMIN))
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product.is_active = False
    db.commit()
    return {"message": "Producto eliminado"}


@router.get("/{product_id}/subcategories", response_model=List[schemas.ProductSubcategoryResponse])
async def get_product_subcategories(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product.subcategories


@router.post("/{product_id}/subcategories", response_model=schemas.ProductSubcategoryResponse)
async def create_product_subcategory(
    product_id: int,
    sub_in: schemas.ProductSubcategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    sub = models.ProductSubcategory(product_id=product_id, **sub_in.model_dump())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.put("/{product_id}/subcategories/{sub_id}", response_model=schemas.ProductSubcategoryResponse)
async def update_product_subcategory(
    product_id: int,
    sub_id: int,
    sub_in: schemas.ProductSubcategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    sub = db.query(models.ProductSubcategory).filter(
        models.ProductSubcategory.id == sub_id,
        models.ProductSubcategory.product_id == product_id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    for field, value in sub_in.model_dump(exclude_unset=True).items():
        setattr(sub, field, value)
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/{product_id}/subcategories/{sub_id}")
async def delete_product_subcategory(
    product_id: int,
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    sub = db.query(models.ProductSubcategory).filter(
        models.ProductSubcategory.id == sub_id,
        models.ProductSubcategory.product_id == product_id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    db.delete(sub)
    db.commit()
    return {"message": "Grupo eliminado"}


@router.post("/{product_id}/subcategories/{sub_id}/items", response_model=schemas.ProductSubcategoryItemResponse)
async def create_subcategory_item(
    product_id: int,
    sub_id: int,
    item_in: schemas.ProductSubcategoryItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    sub = db.query(models.ProductSubcategory).filter(
        models.ProductSubcategory.id == sub_id,
        models.ProductSubcategory.product_id == product_id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    item = models.ProductSubcategoryItem(subcategory_id=sub_id, **item_in.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{product_id}/subcategories/{sub_id}/items/{item_id}")
async def delete_subcategory_item(
    product_id: int,
    sub_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    item = db.query(models.ProductSubcategoryItem).filter(
        models.ProductSubcategoryItem.id == item_id,
        models.ProductSubcategoryItem.subcategory_id == sub_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
    db.delete(item)
    db.commit()
    return {"message": "Ítem eliminado"}


@router.get("/{product_id}/raw-materials", response_model=List[schemas.ProductRawMaterialResponse])
async def get_product_raw_materials(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product.raw_materials


@router.put("/{product_id}/raw-materials", response_model=List[schemas.ProductRawMaterialResponse])
async def set_product_raw_materials(
    product_id: int,
    items: List[schemas.ProductRawMaterialItem],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    for item in items:
        if not db.query(models.RawMaterial).filter(models.RawMaterial.id == item.raw_material_id).first():
            raise HTTPException(status_code=404, detail=f"Materia prima {item.raw_material_id} no encontrada")

    db.query(models.ProductRawMaterial).filter(
        models.ProductRawMaterial.product_id == product_id
    ).delete()

    for item in items:
        db.add(models.ProductRawMaterial(
            product_id=product_id,
            raw_material_id=item.raw_material_id,
            quantity_per_unit=item.quantity_per_unit
        ))

    db.commit()
    return db.query(models.ProductRawMaterial).filter(
        models.ProductRawMaterial.product_id == product_id
    ).all()
