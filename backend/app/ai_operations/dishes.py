"""Smoothed 'dishes on the table' signal from per-frame object detections."""
from collections import deque

from app.ai_operations.geometry import Point, point_in_polygon

# COCO classes that show tableware or food: bottle, wine glass, cup, fork, knife, spoon, bowl,
# banana, apple, sandwich, orange, broccoli, carrot, hot dog, pizza, donut, cake.
DISH_CLASSES = [39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55]


class DishTracker:
    """A table counts as having dishes when at least `needed` of the last `window` frames saw one inside its zone."""

    def __init__(self, zones: dict[int, list[Point]], window: int = 10, needed: int = 6):
        self.zones = zones
        self.needed = needed
        self.history = {table_id: deque(maxlen=window) for table_id in zones}

    def update(self, centres: list[Point]) -> None:
        for table_id, polygon in self.zones.items():
            self.history[table_id].append(any(point_in_polygon(c, polygon) for c in centres))

    def present(self, table_id: int) -> bool:
        return sum(self.history.get(table_id, ())) >= self.needed

    def reset(self) -> None:
        for h in self.history.values():
            h.clear()
