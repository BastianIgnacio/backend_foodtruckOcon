from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from .models import UserRole, CashRegisterStatus, SaleStatus, PaymentMethod, PendingOrderStatus, TaskStatus


# ── Category ──────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    emoji: str = '🍽️'


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    emoji: str
    is_active: bool = True

    class Config:
        from_attributes = True


# ── Auth ──────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str
    user: "UserResponse"


class TokenData(BaseModel):
    username: Optional[str] = None


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    role: UserRole = UserRole.VENDEDOR


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Product ───────────────────────────────────────────────────────────────────

class ProductSubcategoryItemCreate(BaseModel):
    name: str
    extra_price: float = 0


class ProductSubcategoryItemResponse(BaseModel):
    id: int
    name: str
    extra_price: float

    class Config:
        from_attributes = True


class ProductSubcategoryCreate(BaseModel):
    name: str
    max_choices: Optional[int] = None


class ProductSubcategoryUpdate(BaseModel):
    name: Optional[str] = None
    max_choices: Optional[int] = None


class ProductSubcategoryResponse(BaseModel):
    id: int
    name: str
    max_choices: Optional[int]
    items: List[ProductSubcategoryItemResponse] = []

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category: str = "General"
    stock_quantity: int = 0
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    stock_quantity: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    show_in_carousel: Optional[bool] = None
    show_in_carousel2: Optional[bool] = None
    show_in_carousel3: Optional[bool] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    category: str
    stock_quantity: int
    is_out_of_stock: bool
    show_in_carousel: bool = False
    show_in_carousel2: bool = False
    show_in_carousel3: bool = False
    image_url: Optional[str]
    is_active: bool
    created_at: datetime
    subcategories: List[ProductSubcategoryResponse] = []

    class Config:
        from_attributes = True


# ── Raw Material ──────────────────────────────────────────────────────────────

class RawMaterialCreate(BaseModel):
    name: str
    barcode: Optional[str] = None
    unit: str
    quantity: float = 0
    min_quantity: float = 0
    supplier: Optional[str] = None
    cost_per_unit: float = 0


class RawMaterialUpdate(BaseModel):
    name: Optional[str] = None
    barcode: Optional[str] = None
    unit: Optional[str] = None
    min_quantity: Optional[float] = None
    supplier: Optional[str] = None
    cost_per_unit: Optional[float] = None


class RawMaterialEntryCreate(BaseModel):
    quantity: float
    cost_per_unit: float
    supplier: Optional[str] = None
    notes: Optional[str] = None


class RawMaterialEntryResponse(BaseModel):
    id: int
    raw_material_id: int
    quantity: float
    cost_per_unit: float
    supplier: Optional[str]
    notes: Optional[str]
    received_at: datetime
    received_by: Optional[UserResponse]

    class Config:
        from_attributes = True


class RawMaterialResponse(BaseModel):
    id: int
    name: str
    barcode: Optional[str]
    unit: str
    quantity: float
    min_quantity: float
    supplier: Optional[str]
    cost_per_unit: float
    created_at: datetime

    class Config:
        from_attributes = True


class ProductRawMaterialItem(BaseModel):
    raw_material_id: int
    quantity_per_unit: float


class ProductRawMaterialResponse(BaseModel):
    id: int
    raw_material_id: int
    quantity_per_unit: float
    raw_material: RawMaterialResponse

    class Config:
        from_attributes = True


# ── Cash Register ─────────────────────────────────────────────────────────────

class CashRegisterOpen(BaseModel):
    opening_amount: float
    notes: Optional[str] = None


class CashRegisterClose(BaseModel):
    closing_amount: float
    notes: Optional[str] = None


class CashRegisterResponse(BaseModel):
    id: int
    user_id: int
    opening_amount: float
    closing_amount: Optional[float]
    expected_amount: Optional[float]
    difference: Optional[float]
    status: CashRegisterStatus
    notes: Optional[str]
    opened_at: datetime
    closed_at: Optional[datetime]
    user: Optional[UserResponse]

    class Config:
        from_attributes = True


# ── Sale ──────────────────────────────────────────────────────────────────────

class SaleItemCreate(BaseModel):
    product_id: int
    product_name: Optional[str] = None
    quantity: int
    unit_price: float
    notes: Optional[str] = None


class SaleItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str]
    quantity: int
    unit_price: float
    subtotal: float
    notes: Optional[str]

    class Config:
        from_attributes = True


class SaleCreate(BaseModel):
    cash_register_id: int
    customer_name: Optional[str] = None
    items: List[SaleItemCreate]
    discount: float = 0
    payment_method: PaymentMethod
    amount_received: Optional[float] = None
    transaction_code: Optional[str] = None
    notes: Optional[str] = None


class SaleResponse(BaseModel):
    id: int
    sale_number: int
    user_id: int
    cash_register_id: int
    customer_name: Optional[str]
    subtotal: float
    discount: float
    total: float
    payment_method: PaymentMethod
    amount_received: Optional[float]
    change_given: Optional[float]
    status: SaleStatus
    notes: Optional[str]
    created_at: datetime
    items: List[SaleItemResponse]
    seller: Optional[UserResponse]

    class Config:
        from_attributes = True


# ── Pending Orders ────────────────────────────────────────────────────────────

class PendingOrderItemCreate(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: float


class PendingOrderCreate(BaseModel):
    customer_name: str
    items: List[PendingOrderItemCreate]
    notes: Optional[str] = None


class PendingOrderPayment(BaseModel):
    payment_method: PaymentMethod
    amount_received: Optional[float] = None
    transaction_code: Optional[str] = None


class PendingOrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float

    class Config:
        from_attributes = True


class PendingOrderStatusUpdate(BaseModel):
    status: PendingOrderStatus


class PendingOrderResponse(BaseModel):
    id: int
    order_number: int
    customer_name: Optional[str]
    total: float
    status: PendingOrderStatus
    notes: Optional[str]
    created_at: datetime
    attended_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    items: List[PendingOrderItemResponse]

    class Config:
        from_attributes = True


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_user_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    assigned_user_id: Optional[int] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: TaskStatus
    assigned_user_id: Optional[int]
    assigned_user: Optional[UserResponse]
    created_by_id: int
    created_by: Optional[UserResponse]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Settings / Printers ────────────────────────────────────────────────────────

class PrinterResponse(BaseModel):
    name: str
    is_default: bool = False


class DefaultPrinterUpdate(BaseModel):
    printer_name: str


class DefaultPrinterResponse(BaseModel):
    printer_name: Optional[str] = None


class PrintTicketRequest(BaseModel):
    pdf_base64: str
    filename: str = "ticket.pdf"
