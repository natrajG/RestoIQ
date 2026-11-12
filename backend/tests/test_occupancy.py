import pytest

from app.ai_operations.geometry import point_in_polygon, validate_table_polygon
from app.ai_operations.occupancy import OccupancyPhase, OccupancyTracker, PersonPoint

ZONE = [(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4)]


def test_zone_validation_rejects_crossing_and_sliver_polygons():
    with pytest.raises(ValueError, match="must not cross"):
        validate_table_polygon([(0.1, 0.1), (0.4, 0.4), (0.1, 0.4), (0.4, 0.1)])
    with pytest.raises(ValueError, match="too thin"):
        validate_table_polygon([(0.1, 0.1), (0.9, 0.1), (0.9, 0.11), (0.1, 0.11)])


def test_point_on_zone_boundary_counts_as_inside():
    assert point_in_polygon((0.1, 0.25), ZONE)
    assert not point_in_polygon((0.5, 0.25), ZONE)


def test_occupancy_uses_enter_and_leave_hysteresis():
    tracker = OccupancyTracker(
        {4: ("Table 4", ZONE)},
        confidence_threshold=0.5,
        enter_seconds=3,
        leave_seconds=5,
        presence_hold_seconds=1,
    )
    guest = [PersonPoint(0.25, 0.25, 0.9)]

    pending = tracker.update(guest, now=0)
    assert pending[0].current is OccupancyPhase.PENDING_OCCUPIED
    assert tracker.states[4].phase is OccupancyPhase.PENDING_OCCUPIED
    assert tracker.update(guest, now=2.9) == []
    became_occupied = tracker.update(guest, now=3)
    assert became_occupied[0].current is OccupancyPhase.OCCUPIED

    assert tracker.update([], now=4) == []
    assert tracker.states[4].phase is OccupancyPhase.OCCUPIED
    pending_free = tracker.update([], now=5)
    assert pending_free[0].current is OccupancyPhase.PENDING_FREE
    returned_guest = tracker.update(guest, now=6)
    assert returned_guest[0].current is OccupancyPhase.OCCUPIED
    assert tracker.states[4].session_count == 1

    tracker.update([], now=7)
    pending_free = tracker.update([], now=8)
    assert pending_free[0].current is OccupancyPhase.PENDING_FREE
    cleared = tracker.update([], now=11)
    assert cleared[0].current is OccupancyPhase.FREE
    assert tracker.states[4].session_count == 1
    assert tracker.states[4].occupied_seconds_total == pytest.approx(6)


def test_short_presence_and_low_confidence_do_not_mark_occupied():
    tracker = OccupancyTracker({4: ("Table 4", ZONE)}, enter_seconds=3)
    tracker.update([PersonPoint(0.25, 0.25, 0.2)], now=0)
    assert tracker.states[4].phase is OccupancyPhase.FREE
    tracker.update([PersonPoint(0.25, 0.25, 0.9)], now=1)
    tracker.update([], now=2.1)
    assert tracker.states[4].phase is OccupancyPhase.FREE
    assert tracker.states[4].session_count == 0
