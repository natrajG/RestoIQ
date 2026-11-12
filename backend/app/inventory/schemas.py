from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated


class InventoryItemInput(BaseModel):
    restaurant_id: int
    sku: str = Field(min_length=1, max_length=64)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    unit: str = Field(default="unit", max_length=24)
    quantity_on_hand: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)


class StockMovementInput(BaseModel):
    quantity_delta: Decimal
    movement_type: Literal["receipt", "usage", "waste", "adjustment", "return"]
    reference: str | None = Field(default=None, max_length=128)
