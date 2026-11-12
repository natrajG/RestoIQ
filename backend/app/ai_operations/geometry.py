from math import dist

Point = tuple[float, float]
MIN_ZONE_AREA = 0.003
MIN_ZONE_COMPACTNESS = 0.2
EPSILON = 1e-9


def polygon_area(points: list[Point]) -> float:
    return abs(sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )) / 2


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, point: Point) -> bool:
    return (
        min(a[0], b[0]) - EPSILON <= point[0] <= max(a[0], b[0]) + EPSILON
        and min(a[1], b[1]) - EPSILON <= point[1] <= max(a[1], b[1]) + EPSILON
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    ab_c, ab_d = _orientation(a, b, c), _orientation(a, b, d)
    cd_a, cd_b = _orientation(c, d, a), _orientation(c, d, b)
    if (ab_c > EPSILON and ab_d < -EPSILON or ab_c < -EPSILON and ab_d > EPSILON) and (
        cd_a > EPSILON and cd_b < -EPSILON or cd_a < -EPSILON and cd_b > EPSILON
    ):
        return True
    return (
        abs(ab_c) <= EPSILON and _on_segment(a, b, c)
        or abs(ab_d) <= EPSILON and _on_segment(a, b, d)
        or abs(cd_a) <= EPSILON and _on_segment(c, d, a)
        or abs(cd_b) <= EPSILON and _on_segment(c, d, b)
    )


def polygon_self_intersects(points: list[Point]) -> bool:
    count = len(points)
    for first in range(count):
        a, b = points[first], points[(first + 1) % count]
        for second in range(first + 1, count):
            if second == first or second == (first + 1) % count or first == (second + 1) % count:
                continue
            c, d = points[second], points[(second + 1) % count]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def validate_table_polygon(points: list[Point]) -> None:
    if len(points) < 3 or len(points) > 32:
        raise ValueError("A table zone must have 3 to 32 points")
    if any(not (0 <= x <= 1 and 0 <= y <= 1) for x, y in points):
        raise ValueError("Table-zone coordinates must be normalized between 0 and 1")
    if len(set(points)) < 3:
        raise ValueError("A table zone must contain at least three distinct points")
    if polygon_self_intersects(points):
        raise ValueError("Table-zone edges must not cross")
    area = polygon_area(points)
    if area < MIN_ZONE_AREA:
        raise ValueError("Table zone is too small")
    perimeter = sum(dist(points[index], points[(index + 1) % len(points)]) for index in range(len(points)))
    if perimeter == 0 or 4 * 3.141592653589793 * area / (perimeter * perimeter) < MIN_ZONE_COMPACTNESS:
        raise ValueError("Table zone is too thin")


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    inside = False
    x, y = point
    for index, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(index + 1) % len(polygon)]
        if abs(_orientation((x1, y1), (x2, y2), point)) <= EPSILON and _on_segment((x1, y1), (x2, y2), point):
            return True
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
    return inside
