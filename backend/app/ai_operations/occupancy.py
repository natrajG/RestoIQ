from dataclasses import dataclass
from enum import StrEnum

from app.ai_operations.geometry import Point, point_in_polygon, validate_table_polygon


class OccupancyPhase(StrEnum):
    FREE = "FREE"
    PENDING_OCCUPIED = "PENDING_OCCUPIED"
    OCCUPIED = "OCCUPIED"
    PENDING_FREE = "PENDING_FREE"


@dataclass(frozen=True)
class PersonPoint:
    x: float
    y: float
    confidence: float


@dataclass(frozen=True)
class OccupancyTransition:
    table_id: int
    previous: OccupancyPhase
    current: OccupancyPhase
    occurred_at: float


@dataclass
class TableOccupancy:
    table_id: int
    name: str
    phase: OccupancyPhase = OccupancyPhase.FREE
    last_seen_at: float | None = None
    presence_started_at: float | None = None
    occupied_started_at: float | None = None
    occupied_seconds_total: float = 0
    session_count: int = 0


class OccupancyTracker:
    """Per-table presence hysteresis; output must be validated before changing business state."""

    def __init__(
        self,
        zones: dict[int, tuple[str, list[Point]]],
        *,
        confidence_threshold: float = 0.4,
        enter_seconds: float = 5,
        leave_seconds: float = 10,
        presence_hold_seconds: float = 1,
    ) -> None:
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if min(enter_seconds, leave_seconds, presence_hold_seconds) < 0:
            raise ValueError("Occupancy delays cannot be negative")
        self.confidence_threshold = confidence_threshold
        self.enter_seconds = enter_seconds
        self.leave_seconds = leave_seconds
        self.presence_hold_seconds = presence_hold_seconds
        self.zones: dict[int, list[Point]] = {}
        self.states: dict[int, TableOccupancy] = {}
        self.set_zones(zones)

    def set_zones(self, zones: dict[int, tuple[str, list[Point]]]) -> None:
        for _, polygon in zones.values():
            validate_table_polygon(polygon)
        previous = self.states
        self.zones = {table_id: polygon for table_id, (_, polygon) in zones.items()}
        self.states = {
            table_id: previous.get(table_id, TableOccupancy(table_id, name))
            for table_id, (name, _) in zones.items()
        }
        for table_id, (name, _) in zones.items():
            self.states[table_id].name = name

    def update(self, people: list[PersonPoint], now: float) -> list[OccupancyTransition]:
        transitions: list[OccupancyTransition] = []
        valid_points = [
            (person.x, person.y) for person in people
            if person.confidence >= self.confidence_threshold
        ]
        for table_id, polygon in self.zones.items():
            state = self.states[table_id]
            detected = any(point_in_polygon(point, polygon) for point in valid_points)
            if detected:
                state.last_seen_at = now
            present = state.last_seen_at is not None and now - state.last_seen_at <= self.presence_hold_seconds
            if state.phase is OccupancyPhase.FREE and present:
                state.presence_started_at = now
                self._transition(state, OccupancyPhase.PENDING_OCCUPIED, now, transitions)
            elif state.phase is OccupancyPhase.PENDING_OCCUPIED:
                if not present:
                    state.presence_started_at = None
                    self._transition(state, OccupancyPhase.FREE, now, transitions)
                elif state.presence_started_at is not None and now - state.presence_started_at >= self.enter_seconds:
                    state.occupied_started_at = state.presence_started_at
                    state.session_count += 1
                    self._transition(state, OccupancyPhase.OCCUPIED, now, transitions)
            elif state.phase is OccupancyPhase.OCCUPIED and not present:
                self._transition(state, OccupancyPhase.PENDING_FREE, now, transitions)
            elif state.phase is OccupancyPhase.PENDING_FREE:
                if present:
                    self._transition(state, OccupancyPhase.OCCUPIED, now, transitions)
                elif state.last_seen_at is not None and now - state.last_seen_at >= self.leave_seconds:
                    if state.occupied_started_at is not None:
                        state.occupied_seconds_total += max(0, state.last_seen_at - state.occupied_started_at)
                    state.occupied_started_at = None
                    state.presence_started_at = None
                    self._transition(state, OccupancyPhase.FREE, now, transitions)
        return transitions

    def reset_after_outage(self) -> None:
        for table_id, state in self.states.items():
            name = state.name
            self.states[table_id] = TableOccupancy(table_id=table_id, name=name)

    @staticmethod
    def _transition(
        state: TableOccupancy,
        phase: OccupancyPhase,
        now: float,
        transitions: list[OccupancyTransition],
    ) -> None:
        previous = state.phase
        state.phase = phase
        transitions.append(OccupancyTransition(state.table_id, previous, phase, now))
