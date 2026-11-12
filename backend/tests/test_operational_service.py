from decimal import Decimal
from datetime import datetime, timezone

import pytest

from app.ai_operations.repository import MenuDemandPoint
from app.ai_operations.service import menu_recommendations
from app.ai_operations.service import create_staff_task
from app.auth.dependencies import Principal
from app.inventory.schemas import StockMovementInput
from app.inventory.service import apply_stock_movement
from app.models import InventoryItem, StaffTask


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.next_id = 1

    def add(self, item: object) -> None:
        self.added.append(item)

    def scalar(self, _query: object) -> None:
        return None

    def flush(self) -> None:
        for item in self.added:
            if getattr(item, "id", None) is None:
                setattr(item, "id", self.next_id)
                self.next_id += 1


def test_native_staff_task_targets_cleaning_role():
    db = FakeSession()
    task = create_staff_task(
        db, Principal(3, 9, "manager", "manager@example.test"), 12,
        "clean_table", "cleaner", "Clean table 4", table_id=4,
    )
    assert task.target_role == "cleaning"
    assert task.created_by == 3


def test_stock_movement_rejects_negative_inventory():
    item = InventoryItem(id=5, quantity_on_hand=Decimal("2.000"))
    body = StockMovementInput(quantity_delta=Decimal("3"), movement_type="usage")
    with pytest.raises(ValueError, match="inventory negative"):
        apply_stock_movement(item, body, tenant_id=9, outlet_id=12)


def test_stock_movement_normalizes_usage_as_negative():
    item = InventoryItem(id=5, quantity_on_hand=Decimal("3.000"))
    body = StockMovementInput(quantity_delta=Decimal("2"), movement_type="usage")
    movement = apply_stock_movement(item, body, tenant_id=9, outlet_id=12)
    assert item.quantity_on_hand == Decimal("1.000")
    assert movement.quantity_delta == Decimal("-2")


def test_menu_recommendation_uses_day_window_and_festival_context():
    points = [
        MenuDemandPoint("Masala Dosa", 3, datetime(2026, 11, 2, 7, 45, tzinfo=timezone.utc)),
        MenuDemandPoint("Masala Dosa", 2, datetime(2026, 11, 9, 7, 15, tzinfo=timezone.utc)),
        MenuDemandPoint("Idli Sambar", 2, datetime(2026, 11, 9, 7, 40, tzinfo=timezone.utc)),
        MenuDemandPoint("Filter Coffee", 4, datetime(2026, 11, 9, 7, 50, tzinfo=timezone.utc)),
        MenuDemandPoint("Masala Dosa", 4, datetime(2026, 11, 10, 7, 30, tzinfo=timezone.utc)),
        MenuDemandPoint("Idli Sambar", 3, datetime(2026, 11, 10, 7, 35, tzinfo=timezone.utc)),
        MenuDemandPoint("Filter Coffee", 5, datetime(2026, 11, 10, 7, 45, tzinfo=timezone.utc)),
        MenuDemandPoint("Veg Biryani", 2, datetime(2026, 10, 27, 13, 15, tzinfo=timezone.utc)),
        MenuDemandPoint("Veg Biryani", 1, datetime(2026, 10, 20, 13, 20, tzinfo=timezone.utc)),
        MenuDemandPoint("Paneer Tikka", 2, datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)),
        MenuDemandPoint("Paneer Tikka", 2, datetime(2026, 10, 28, 13, 10, tzinfo=timezone.utc)),
        MenuDemandPoint("Paneer Tikka", 1, datetime(2026, 11, 4, 13, 5, tzinfo=timezone.utc)),
        MenuDemandPoint("Masala Chai", 2, datetime(2026, 10, 29, 16, 15, tzinfo=timezone.utc)),
        MenuDemandPoint("Masala Chai", 2, datetime(2026, 11, 5, 16, 25, tzinfo=timezone.utc)),
        MenuDemandPoint("Cold Coffee", 1, datetime(2026, 10, 30, 16, 10, tzinfo=timezone.utc)),
        MenuDemandPoint("Cold Coffee", 1, datetime(2026, 11, 6, 16, 20, tzinfo=timezone.utc)),
        MenuDemandPoint("Jeera Rice", 1, datetime(2026, 11, 1, 13, 30, tzinfo=timezone.utc)),
        MenuDemandPoint("Jeera Rice", 1, datetime(2026, 11, 8, 13, 40, tzinfo=timezone.utc)),
        MenuDemandPoint("Garlic Naan", 2, datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)),
        MenuDemandPoint("Garlic Naan", 2, datetime(2026, 11, 10, 14, 5, tzinfo=timezone.utc)),
    ]
    recommendations = menu_recommendations(
        points,
        "Asia/Kolkata",
        now_utc_dt=datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc),
        active_festival="Diwali",
    )
    assert recommendations
    top_items = recommendations[0]["evidence"]["top_items"]
    assert top_items[0]["item"] in {"Filter Coffee", "Masala Dosa"}
    assert recommendations[0]["evidence"]["active_festival"] == "Diwali"
