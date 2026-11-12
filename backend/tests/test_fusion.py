from app.ai_operations.fusion import FloorFusion, phases_to_occupied
from app.ai_operations.occupancy import OccupancyPhase


def test_any_camera_occupied_wins_and_overlap_is_fused():
    fusion = FloorFusion()
    fusion.set_camera(1, {10: False, 11: True})
    fusion.set_camera(2, {10: True})
    assert fusion.table_state(10) is True
    assert fusion.table_state(11) is True


def test_uncovered_and_offline_tables_are_unknown_not_free():
    fusion = FloorFusion()
    fusion.set_camera(1, {10: False})
    assert fusion.table_state(99) is None
    fusion.set_camera(1, None)
    assert fusion.table_state(10) is None


def test_changes_only_reports_transitions():
    fusion = FloorFusion()
    fusion.set_camera(1, {10: False})
    assert fusion.changes() == [(10, False)]
    assert fusion.changes() == []
    fusion.set_camera(1, {10: True})
    assert fusion.changes() == [(10, True)]
    fusion.set_camera(1, None)
    assert fusion.changes() == [(10, None)]


def test_pending_free_still_counts_as_occupied():
    states = phases_to_occupied({1: OccupancyPhase.PENDING_FREE, 2: OccupancyPhase.PENDING_OCCUPIED, 3: OccupancyPhase.FREE})
    assert states == {1: True, 2: False, 3: False}
