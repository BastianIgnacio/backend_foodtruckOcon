import base64
import os
import shutil
import subprocess
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from .. import models, schemas
from ..auth import require_roles

router = APIRouter()

staff_only = require_roles(models.UserRole.ADMIN, models.UserRole.VENDEDOR)

DEFAULT_PRINTER_KEY = "default_printer"

SUMATRA_CANDIDATES = [
    os.path.expandvars(r"%ProgramFiles%\SumatraPDF\SumatraPDF.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\SumatraPDF\SumatraPDF.exe"),
    os.path.expandvars(r"%LocalAppData%\SumatraPDF\SumatraPDF.exe"),
]


def find_sumatra() -> Optional[str]:
    if settings.SUMATRA_PDF_PATH and os.path.isfile(settings.SUMATRA_PDF_PATH):
        return settings.SUMATRA_PDF_PATH
    for path in SUMATRA_CANDIDATES:
        if os.path.isfile(path):
            return path
    return shutil.which("SumatraPDF.exe") or shutil.which("SumatraPDF")


def list_system_printers() -> List[str]:
    try:
        import win32print
    except ImportError:
        return []
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return [p[2] for p in win32print.EnumPrinters(flags)]


def get_default_printer_name(db: Session) -> Optional[str]:
    setting = db.query(models.AppSetting).filter(models.AppSetting.key == DEFAULT_PRINTER_KEY).first()
    return setting.value if setting else None


@router.get("/", response_model=List[schemas.PrinterResponse])
async def get_printers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    names = list_system_printers()
    default_name = get_default_printer_name(db)
    return [schemas.PrinterResponse(name=n, is_default=(n == default_name)) for n in names]


@router.get("/default", response_model=schemas.DefaultPrinterResponse)
async def get_default_printer(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    return schemas.DefaultPrinterResponse(printer_name=get_default_printer_name(db))


@router.put("/default", response_model=schemas.DefaultPrinterResponse)
async def set_default_printer(
    data: schemas.DefaultPrinterUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    if data.printer_name not in list_system_printers():
        raise HTTPException(status_code=400, detail="Impresora no encontrada en el sistema")

    setting = db.query(models.AppSetting).filter(models.AppSetting.key == DEFAULT_PRINTER_KEY).first()
    if setting:
        setting.value = data.printer_name
    else:
        setting = models.AppSetting(key=DEFAULT_PRINTER_KEY, value=data.printer_name)
        db.add(setting)
    db.commit()
    return schemas.DefaultPrinterResponse(printer_name=data.printer_name)


@router.post("/print")
async def print_ticket(
    data: schemas.PrintTicketRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(staff_only)
):
    printer_name = get_default_printer_name(db)
    if not printer_name:
        raise HTTPException(status_code=400, detail="No hay una impresora por defecto configurada. Ve a Configuraciones para seleccionar una.")

    sumatra = find_sumatra()
    if not sumatra:
        raise HTTPException(status_code=500, detail="No se encontró SumatraPDF.exe en este computador. Instálalo para poder imprimir.")

    try:
        pdf_bytes = base64.b64decode(data.pdf_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="PDF inválido")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        result = subprocess.run(
            [sumatra, "-print-to", printer_name, "-exit-when-done", tmp_path],
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            detail = result.stderr.decode(errors="ignore").strip() or f"código de salida {result.returncode}"
            raise HTTPException(status_code=500, detail=f"Error al imprimir: {detail}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="La impresora no respondió a tiempo")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return {"message": f"Ticket enviado a {printer_name}"}
