from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, current_principal, require_outlet_access, require_roles
from app.core.audit import audit
from app.db import get_db
from app.models import InventoryItem, StockMovement
from app.inventory.schemas import InventoryItemInput, StockMovementInput
from app.inventory.repository import add_item, item_by_id, items_for_outlet
from app.inventory.service import apply_stock_movement

router = APIRouter(prefix="/api/v1/outlets/{outlet_id}/inventory", tags=["inventory"])
MANAGERS = ("owner", "manager", "admin")


@router.get("")
def list_inventory(outlet_id: int, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    require_outlet_access(db, principal, outlet_id)
    rows = items_for_outlet(db, principal.tenant_id, outlet_id)
    return [{
        "id": item.id, "sku": item.sku, "name": item.name, "unit": item.unit,
        "quantity_on_hand": str(item.quantity_on_hand), "reorder_level": str(item.reorder_level),
        "unit_cost": str(item.unit_cost), "low_stock": item.quantity_on_hand <= item.reorder_level,
    } for item in rows]


@router.post("", status_code=201)
def create_inventory_item(
    outlet_id: int,
    body: InventoryItemInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS)),
):
    require_outlet_access(db, principal, outlet_id)
    if body.restaurant_id != outlet_id:
        raise HTTPException(422, "Outlet ID mismatch")
    item = InventoryItem(
        tenant_id=principal.tenant_id, restaurant_id=outlet_id,
        **body.model_dump(exclude={"restaurant_id"}),
    )
    add_item(db, item)
    if item.quantity_on_hand:
        db.add(StockMovement(
            tenant_id=principal.tenant_id, restaurant_id=outlet_id, inventory_item_id=item.id,
            quantity_delta=item.quantity_on_hand, movement_type="receipt", reference="opening balance",
        ))
    audit(db, principal, "inventory_item_created", "inventory_item", item.id)
    return {"id": item.id, "name": item.name, "quantity_on_hand": str(item.quantity_on_hand)}


@router.post("/{item_id}/movements")
def stock_movement(
    outlet_id: int,
    item_id: int,
    body: StockMovementInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(*MANAGERS, "waiter", "kitchen")),
):
    require_outlet_access(db, principal, outlet_id)
    item = item_by_id(db, principal.tenant_id, outlet_id, item_id)
    if not item:
        raise HTTPException(404, "Inventory item not found")
    try:
        movement = apply_stock_movement(item, body, principal.tenant_id, outlet_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.add(movement)
    db.flush()
    audit(db, principal, "stock_movement_recorded", "inventory_item", item.id, {"delta": str(movement.quantity_delta)})
    return {"item_id": item.id, "quantity_on_hand": str(item.quantity_on_hand), "movement_id": movement.id}
