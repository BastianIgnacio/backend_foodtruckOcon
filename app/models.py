import enum
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Enum as SQLEnum, Text
)
from sqlalchemy.orm import relationship
from .database import Base
from .utils import now_santiago


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    VENDEDOR = "VENDEDOR"


class PendingOrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    WAITING = "WAITING"
    READY = "READY"
    ATTENDED = "ATTENDED"
    CANCELLED = "CANCELLED"


class CashRegisterStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class SaleStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    CARD = "CARD"
    TRANSFER = "TRANSFER"
    JUNAEB = "JUNAEB"


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    emoji = Column(String(10), default='🍽️')
    is_active = Column(Boolean, default=True, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.VENDEDOR, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=now_santiago)

    sales = relationship("Sale", back_populates="seller")
    cash_registers = relationship("CashRegister", back_populates="user")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    category = Column(String(50), default="General")
    stock_quantity = Column(Integer, default=0)
    is_out_of_stock = Column(Boolean, default=False)
    show_in_carousel = Column(Boolean, default=False)
    show_in_carousel2 = Column(Boolean, default=False)
    show_in_carousel3 = Column(Boolean, default=False)
    image_url = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=now_santiago)
    updated_at = Column(DateTime(timezone=True), onupdate=now_santiago)

    sale_items = relationship("SaleItem", back_populates="product")
    raw_materials = relationship("ProductRawMaterial", back_populates="product", cascade="all, delete-orphan")
    subcategories = relationship("ProductSubcategory", back_populates="product", cascade="all, delete-orphan", order_by="ProductSubcategory.id")


class ProductSubcategory(Base):
    __tablename__ = "product_subcategories"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    name = Column(String(100), nullable=False)
    max_choices = Column(Integer, nullable=True)  # None = elección libre

    product = relationship("Product", back_populates="subcategories")
    items = relationship("ProductSubcategoryItem", back_populates="subcategory",
                         cascade="all, delete-orphan", order_by="ProductSubcategoryItem.id")


class ProductSubcategoryItem(Base):
    __tablename__ = "product_subcategory_items"

    id = Column(Integer, primary_key=True, index=True)
    subcategory_id = Column(Integer, ForeignKey("product_subcategories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    extra_price = Column(Float, nullable=False, default=0)

    subcategory = relationship("ProductSubcategory", back_populates="items")


class ProductRawMaterial(Base):
    __tablename__ = "product_raw_materials"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=False)
    quantity_per_unit = Column(Float, nullable=False)

    product = relationship("Product", back_populates="raw_materials")
    raw_material = relationship("RawMaterial")


class RawMaterial(Base):
    __tablename__ = "raw_materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    barcode = Column(String(100), unique=True, nullable=True)
    unit = Column(String(20), nullable=False)
    quantity = Column(Float, default=0)
    min_quantity = Column(Float, default=0)
    supplier = Column(String(100))
    cost_per_unit = Column(Float, default=0)
    created_at = Column(DateTime(timezone=True), default=now_santiago)
    updated_at = Column(DateTime(timezone=True), onupdate=now_santiago)

    entries = relationship("RawMaterialEntry", back_populates="raw_material")


class RawMaterialEntry(Base):
    __tablename__ = "raw_material_entries"

    id = Column(Integer, primary_key=True, index=True)
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"))
    quantity = Column(Float, nullable=False)
    cost_per_unit = Column(Float, nullable=False)
    supplier = Column(String(100))
    received_by_id = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)
    received_at = Column(DateTime(timezone=True), default=now_santiago)

    raw_material = relationship("RawMaterial", back_populates="entries")
    received_by = relationship("User")


class CashRegister(Base):
    __tablename__ = "cash_registers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    opening_amount = Column(Float, nullable=False)
    closing_amount = Column(Float)
    expected_amount = Column(Float)
    difference = Column(Float)
    status = Column(SQLEnum(CashRegisterStatus), default=CashRegisterStatus.OPEN)
    notes = Column(Text)
    opened_at = Column(DateTime(timezone=True), default=now_santiago)
    closed_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="cash_registers")
    sales = relationship("Sale", back_populates="cash_register")


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    sale_number = Column(Integer, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    cash_register_id = Column(Integer, ForeignKey("cash_registers.id"))
    customer_name = Column(String(100))
    subtotal = Column(Float, nullable=False)
    discount = Column(Float, default=0)
    total = Column(Float, nullable=False)
    payment_method = Column(SQLEnum(PaymentMethod), nullable=False)
    amount_received = Column(Float)
    change_given = Column(Float)
    status = Column(SQLEnum(SaleStatus), default=SaleStatus.COMPLETED)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=now_santiago)

    seller = relationship("User", back_populates="sales")
    cash_register = relationship("CashRegister", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    product_name = Column(String(100))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    notes = Column(Text)

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")


class PendingOrder(Base):
    __tablename__ = "pending_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(Integer, unique=True, index=True)
    customer_name = Column(String(100))
    total = Column(Float, nullable=False)
    status = Column(SQLEnum(PendingOrderStatus), default=PendingOrderStatus.WAITING)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=now_santiago)
    attended_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))

    items = relationship("PendingOrderItem", back_populates="order", cascade="all, delete-orphan")


class PendingOrderItem(Base):
    __tablename__ = "pending_order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("pending_orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    product_name = Column(String(100))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    order = relationship("PendingOrder", back_populates="items")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(255))


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_santiago)
    updated_at = Column(DateTime(timezone=True), onupdate=now_santiago)

    assigned_user = relationship("User", foreign_keys=[assigned_user_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
