from app.ai_operations.dishes import DishTracker

SQUARE = [(0.2, 0.2), (0.6, 0.2), (0.6, 0.6), (0.2, 0.6)]


def test_dishes_need_several_frames_inside_the_zone():
    t = DishTracker({1: SQUARE})
    for _ in range(5):
        t.update([(0.4, 0.4)])
    assert t.present(1) is False
    t.update([(0.4, 0.4)])
    assert t.present(1) is True


def test_dishes_outside_the_zone_or_one_noisy_frame_do_not_count():
    t = DishTracker({1: SQUARE})
    for _ in range(10):
        t.update([(0.9, 0.9)])
    assert t.present(1) is False
    t.update([(0.4, 0.4)])
    assert t.present(1) is False


def test_dishes_clear_after_the_table_is_cleared():
    t = DishTracker({1: SQUARE})
    for _ in range(10):
        t.update([(0.4, 0.4)])
    assert t.present(1) is True
    for _ in range(5):
        t.update([])
    assert t.present(1) is False
