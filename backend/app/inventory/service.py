from decimal import Decimal

from app.inventory.schemas import StockMovementInput
from app.models import InventoryItem, StockMovement


def normalized_stock_delta(body: StockMovementInput) -> Decimal:
    if body.movement_type in {"usage", "waste"}:
        return -abs(body.quantity_delta)
    if body.movement_type in {"receipt", "return"}:
        return abs(body.quantity_delta)
    return body.quantity_delta


def apply_stock_movement(
    item: InventoryItem,
    body: StockMovementInput,
    tenant_id: int,
    outlet_id: int,
) -> StockMovement:
    delta = normalized_stock_delta(body)
    if item.quantity_on_hand + delta < 0:
        raise ValueError("Stock movement would make inventory negative")
    item.quantity_on_hand += delta
    return StockMovement(
        tenant_id=tenant_id,
        restaurant_id=outlet_id,
        inventory_item_id=item.id,
        quantity_delta=delta,
        movement_type=body.movement_type,
        reference=body.reference,
    )
