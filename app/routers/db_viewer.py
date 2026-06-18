from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from ..database import get_db, engine
from ..auth import require_roles
from .. import models

router = APIRouter()

admin_only = require_roles(models.UserRole.ADMIN)


@router.get("/")
async def get_database(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_only)
):
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())

    result = []
    for table_name in table_names:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        rows_raw = db.execute(text(f'SELECT * FROM "{table_name}"')).fetchall()
        rows = [dict(zip(columns, row)) for row in rows_raw]
        result.append({
            "table": table_name,
            "columns": columns,
            "rows": rows,
            "count": len(rows),
        })

    return result
