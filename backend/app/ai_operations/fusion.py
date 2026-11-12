"""Combine per-camera table occupancy into one state per table.

A table is occupied if ANY online camera covering it reports it occupied. A table whose
cameras are all offline (or that no camera covers) is unknown, never "free".
"""
from app.ai_operations.occupancy import OccupancyPhase

OCCUPIED_PHASES = {OccupancyPhase.OCCUPIED, OccupancyPhase.PENDING_FREE}


def phases_to_occupied(phases: dict[int, OccupancyPhase]) -> dict[int, bool]:
    return {table_id: phase in OCCUPIED_PHASES for table_id, phase in phases.items()}


class FloorFusion:
    def __init__(self) -> None:
        self.cameras: dict[int, dict[int, bool] | None] = {}
        self.published: dict[int, bool | None] = {}

    def set_camera(self, camera_id: int, table_states: dict[int, bool] | None) -> None:
        """table_states=None marks the camera as offline."""
        self.cameras[camera_id] = table_states

    def remove_camera(self, camera_id: int) -> None:
        self.cameras.pop(camera_id, None)

    def table_state(self, table_id: int) -> bool | None:
        seen = [states[table_id] for states in self.cameras.values() if states is not None and table_id in states]
        if not seen:
            return None
        return any(seen)

    def known_tables(self) -> set[int]:
        tables = set(self.published)
        for states in self.cameras.values():
            tables.update(states or {})
        return tables

    def changes(self) -> list[tuple[int, bool | None]]:
        """Tables whose fused state differs from what was last published."""
        changed = []
        for table_id in sorted(self.known_tables()):
            state = self.table_state(table_id)
            if table_id not in self.published:
                if state is None:
                    continue
            elif self.published[table_id] == state:
                continue
            self.published[table_id] = state
            changed.append((table_id, state))
        return changed
