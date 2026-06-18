import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from ..auth import require_roles
from .. import models

router = APIRouter()

staff_only = require_roles(models.UserRole.ADMIN, models.UserRole.VENDEDOR)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "images")
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: models.User = Depends(staff_only)
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido. Usa JPG, PNG, WEBP o GIF.")

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="La imagen no puede superar los 5 MB.")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(STATIC_DIR, filename)

    os.makedirs(STATIC_DIR, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(contents)

    return {"url": f"/static/images/{filename}"}
