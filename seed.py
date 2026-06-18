"""Seed inicial: crea admin, vendedor y productos de ejemplo."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, engine, Base
from app import models
from app.auth import get_password_hash

Base.metadata.create_all(bind=engine)

db = SessionLocal()

def seed():
    if db.query(models.User).first():
        print("La base de datos ya tiene datos. Omitiendo seed.")
        return

    admin = models.User(
        username="admin",
        email="admin@foodtruck.com",
        full_name="Administrador",
        hashed_password=get_password_hash("admin123"),
        role=models.UserRole.ADMIN,
    )
    vendedor = models.User(
        username="vendedor1",
        email="vendedor1@foodtruck.com",
        full_name="Juan Pérez",
        hashed_password=get_password_hash("vendedor123"),
        role=models.UserRole.VENDEDOR,
    )
    db.add_all([admin, vendedor])

    products = [
        models.Product(name="Hot Dog Clásico", description="Hot dog con mostaza y ketchup", price=2500, category="Hot Dogs", stock_quantity=50),
        models.Product(name="Hot Dog Completo", description="Hot dog con todo los toppings", price=3200, category="Hot Dogs", stock_quantity=50),
        models.Product(name="Hamburguesa Simple", description="Carne, lechuga, tomate", price=3500, category="Hamburguesas", stock_quantity=30),
        models.Product(name="Hamburguesa Doble", description="Doble carne, queso", price=4500, category="Hamburguesas", stock_quantity=30),
        models.Product(name="Papas Fritas", description="Porción de papas fritas", price=1500, category="Acompañamientos", stock_quantity=100),
        models.Product(name="Bebida Cola", description="Lata 350ml", price=800, category="Bebidas", stock_quantity=200),
        models.Product(name="Agua Mineral", description="Botella 500ml", price=600, category="Bebidas", stock_quantity=200),
        models.Product(name="Jugo Natural", description="Jugo de frutas naturales", price=1200, category="Bebidas", stock_quantity=50),
    ]
    db.add_all(products)

    raw_materials = [
        models.RawMaterial(name="Pan para hot dog", unit="unidades", quantity=100, min_quantity=20, supplier="Panadería El Sol", cost_per_unit=150),
        models.RawMaterial(name="Salchicha", unit="kg", quantity=10, min_quantity=2, supplier="Frigorífico Central", cost_per_unit=4500),
        models.RawMaterial(name="Carne molida", unit="kg", quantity=15, min_quantity=3, supplier="Frigorífico Central", cost_per_unit=6000),
        models.RawMaterial(name="Pan hamburguesa", unit="unidades", quantity=60, min_quantity=15, supplier="Panadería El Sol", cost_per_unit=200),
        models.RawMaterial(name="Papas", unit="kg", quantity=20, min_quantity=5, supplier="Verdulería Fresca", cost_per_unit=800),
        models.RawMaterial(name="Aceite de fritura", unit="litros", quantity=5, min_quantity=1, supplier="Distribuidora Norte", cost_per_unit=2500),
    ]
    db.add_all(raw_materials)

    db.commit()
    print("OK Seed completado exitosamente")
    print("  Admin:    admin / admin123")
    print("  Vendedor: vendedor1 / vendedor123")


if __name__ == "__main__":
    seed()
    db.close()
