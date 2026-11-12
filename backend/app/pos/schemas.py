from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class MenuItemInput(BaseModel):
    restaurant_id: int
    category_id: int | None = None
    name: ShortText
    sku: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    price: Decimal = Field(ge=0, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    tax_rate: Decimal = Field(default=Decimal("5"), ge=0, le=100, decimal_places=3)


class OrderLineInput(BaseModel):
    menu_item_id: int
    quantity: int = Field(ge=1, le=100)
    notes: str | None = Field(default=None, max_length=300)
    variant_id: int | None = None
    addon_ids: list[int] = Field(default_factory=list, max_length=10)


class OrderInput(BaseModel):
    restaurant_id: int
    table_id: int | None = None
    customer_id: int | None = None
    order_type: Literal["dine_in", "takeaway", "delivery", "online"] = "dine_in"
    contact_name: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, pattern=r"^[0-9+ -]{7,20}$")
    delivery_address: str | None = Field(default=None, max_length=400)
    covers: int | None = Field(default=None, ge=1, le=100)
    scheduled_for: datetime | None = None
    advance_amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    advance_method: Literal["cash", "card_external", "upi_external", "bank_transfer", "other"] = "cash"
    remark: str | None = Field(default=None, max_length=300)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    items: list[OrderLineInput] = Field(min_length=1, max_length=100)


class OrderEventInput(BaseModel):
    event_type: Literal[
        "KOT_ACCEPTED", "PREPARATION_STARTED", "FOOD_READY", "FOOD_PICKED_UP",
        "FOOD_DELIVERED", "BILL_REQUESTED", "ORDER_COMPLETED", "CUSTOMER_DEPARTED",
    ]
    notes: str | None = Field(default=None, max_length=300)


class PaymentInput(BaseModel):
    method: Literal["cash", "card_external", "upi_external", "bank_transfer", "other", "customer_account"]
    amount: Decimal = Field(gt=0, decimal_places=2)
    reference: str | None = Field(default=None, max_length=128)


class TableCorrectionInput(BaseModel):
    status: Literal["FREE", "OCCUPIED", "DIRTY", "CLEANING", "READY", "RESERVED", "BILLING"]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]


class RefundInput(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
