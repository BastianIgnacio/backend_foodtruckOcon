from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
from ..auth import require_roles

router = APIRouter()


@router.get("/", response_model=List[schemas.CategoryResponse])
async def get_categories(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    query = db.query(models.Category).order_by(models.Category.name)
    if active_only:
        query = query.filter(models.Category.is_active == True)
    return query.all()


@router.post("/", response_model=schemas.CategoryResponse)
async def create_category(
    cat_in: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.UserRole.ADMIN))
):
    if db.query(models.Category).filter(models.Category.name == cat_in.name).first():
        raise HTTPException(status_code=400, detail="Ya existe una categoría con ese nombre")
    cat = models.Category(**cat_in.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{category_id}", response_model=schemas.CategoryResponse)
async def update_category(
    category_id: int,
    cat_in: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.UserRole.ADMIN))
):
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    data = cat_in.model_dump(exclude_unset=True)

    # Si se está cambiando el nombre, actualizar los productos que la referencian
    if 'name' in data and data['name'] != cat.name:
        if db.query(models.Category).filter(models.Category.name == data['name']).first():
            raise HTTPException(status_code=400, detail="Ya existe una categoría con ese nombre")
        db.query(models.Product).filter(models.Product.category == cat.name).update({"category": data['name']})

    # Efecto secundario: desactivar categoría → desactivar todos sus productos
    if data.get('is_active') is False:
        db.query(models.Product).filter(
            models.Product.category == cat.name
        ).update({"is_active": False})

    for field, value in data.items():
        setattr(cat, field, value)

    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.UserRole.ADMIN))
):
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    db.query(models.Product).filter(
        models.Product.category == cat.name
    ).update({"is_active": False})

    db.delete(cat)
    db.commit()
    return {"message": "Categoría eliminada"}
