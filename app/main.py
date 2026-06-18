import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from jose import jwt, JWTError

from .database import engine, Base, SessionLocal
from .config import settings
from . import models
from .websocket_manager import manager
from .routers import auth, users, products, raw_materials, cash_register, sales, pending_orders, upload, categories, db_viewer, printers, tasks


STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    os.makedirs(os.path.join(STATIC_DIR, "images"), exist_ok=True)
    # Migrations for columns added after initial DB creation
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS show_in_carousel BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS show_in_carousel2 BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS show_in_carousel3 BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE raw_materials ADD COLUMN IF NOT EXISTS barcode VARCHAR(100)",
            "ALTER TABLE pending_orders ADD COLUMN IF NOT EXISTS attended_at TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE pending_orders ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP WITH TIME ZONE",
        ]:
            conn.execute(text(stmt))
            conn.commit()
    # Seed initial categories
    INITIAL_CATEGORIES = [
        {"name": "Hot Dogs", "emoji": "🌭"},
        {"name": "Hamburguesas", "emoji": "🍔"},
        {"name": "Acompañamientos", "emoji": "🍟"},
        {"name": "Bebidas", "emoji": "🥤"},
        {"name": "General", "emoji": "🍽️"},
        {"name": "Otro", "emoji": "🥘"},
    ]
    db = SessionLocal()
    try:
        if db.query(models.Category).count() == 0:
            for cat_data in INITIAL_CATEGORIES:
                db.add(models.Category(**cat_data))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="FoodTruck Manager API",
    description="Sistema de gestión para negocio de comida",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios"])
app.include_router(products.router, prefix="/api/products", tags=["Productos"])
app.include_router(raw_materials.router, prefix="/api/raw-materials", tags=["Materias Primas"])
app.include_router(cash_register.router, prefix="/api/cash-registers", tags=["Caja"])
app.include_router(sales.router, prefix="/api/sales", tags=["Ventas"])
app.include_router(pending_orders.router, prefix="/api/pending-orders", tags=["Pedidos en Espera"])
app.include_router(upload.router, prefix="/api/upload", tags=["Archivos"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categorías"])
app.include_router(db_viewer.router, prefix="/api/db", tags=["Base de Datos"])
app.include_router(printers.router, prefix="/api/printers", tags=["Impresoras"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tareas"])

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if not username:
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.close(code=1008)
        return

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(
            models.User.username == username,
            models.User.is_active == True
        ).first()
        if not user:
            await websocket.close(code=1008)
            return

        await manager.connect(websocket, user.id, user.role.value)
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            manager.disconnect(websocket)
    finally:
        db.close()


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "FoodTruck Manager"}
