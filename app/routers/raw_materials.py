from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
from ..auth import require_roles
from ..websocket_manager import manager

router = APIRouter()

staff_only = require_roles(models.UserRole.ADMIN, models.UserRole.VENDEDOR)


@router.get("/", response_model=List[schemas.RawMaterialResponse])
async def get_raw_materials(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    return db.query(models.RawMaterial).all()


@router.post("/", response_model=schemas.RawMaterialResponse)
async def create_raw_material(
    material_in: schemas.RawMaterialCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    material = models.RawMaterial(**material_in.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.put("/{material_id}", response_model=schemas.RawMaterialResponse)
async def update_raw_material(
    material_id: int,
    material_in: schemas.RawMaterialUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    material = db.query(models.RawMaterial).filter(
        models.RawMaterial.id == material_id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="Materia prima no encontrada")

    for field, value in material_in.model_dump(exclude_unset=True).items():
        setattr(material, field, value)

    db.commit()
    db.refresh(material)
    return material


@router.post("/{material_id}/entries", response_model=schemas.RawMaterialEntryResponse)
async def add_entry(
    material_id: int,
    entry_in: schemas.RawMaterialEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    material = db.query(models.RawMaterial).filter(
        models.RawMaterial.id == material_id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="Materia prima no encontrada")

    entry = models.RawMaterialEntry(
        raw_material_id=material_id,
        received_by_id=current_user.id,
        **entry_in.model_dump()
    )
    db.add(entry)
    material.quantity += entry_in.quantity
    material.cost_per_unit = entry_in.cost_per_unit
    if entry_in.supplier:
        material.supplier = entry_in.supplier

    db.commit()
    db.refresh(entry)

    await manager.broadcast({
        "type": "raw_material_received",
        "material": {"id": material.id, "name": material.name, "quantity": material.quantity}
    })
    return entry


@router.delete("/{material_id}", status_code=204)
async def delete_raw_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    material = db.query(models.RawMaterial).filter(
        models.RawMaterial.id == material_id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="Materia prima no encontrada")
    db.delete(material)
    db.commit()


@router.get("/{material_id}/entries", response_model=List[schemas.RawMaterialEntryResponse])
async def get_entries(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    return db.query(models.RawMaterialEntry).filter(
        models.RawMaterialEntry.raw_material_id == material_id
    ).order_by(models.RawMaterialEntry.received_at.desc()).all()
