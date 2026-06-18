from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
from ..auth import require_roles

router = APIRouter()

admin_only = require_roles(models.UserRole.ADMIN)


@router.get("/", response_model=List[schemas.TaskResponse])
async def get_tasks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_only)
):
    return db.query(models.Task).order_by(models.Task.created_at.desc()).all()


@router.post("/", response_model=schemas.TaskResponse)
async def create_task(
    task_in: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_only)
):
    if task_in.assigned_user_id:
        assigned = db.query(models.User).filter(
            models.User.id == task_in.assigned_user_id,
            models.User.role == models.UserRole.ADMIN,
            models.User.is_active == True
        ).first()
        if not assigned:
            raise HTTPException(status_code=400, detail="Solo se pueden asignar usuarios administradores activos")

    task = models.Task(
        title=task_in.title,
        description=task_in.description,
        assigned_user_id=task_in.assigned_user_id,
        created_by_id=current_user.id
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=schemas.TaskResponse)
async def update_task(
    task_id: int,
    task_in: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_only)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    if task_in.assigned_user_id is not None:
        assigned = db.query(models.User).filter(
            models.User.id == task_in.assigned_user_id,
            models.User.role == models.UserRole.ADMIN,
            models.User.is_active == True
        ).first()
        if not assigned:
            raise HTTPException(status_code=400, detail="Solo se pueden asignar usuarios administradores activos")

    for field, value in task_in.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_only)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    db.delete(task)
    db.commit()
    return {"ok": True}
