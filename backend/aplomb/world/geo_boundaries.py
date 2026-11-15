"""Bounding-box queries for the captured metropolitan France ADM1 polygons."""

from __future__ import annotations


def _segment_hits_box(a: list, b: list, box: tuple[float, float, float, float]) -> bool:
    """Liang–Barsky clipping, including boundary contact."""
    west, south, east, north = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    low, high = 0.0, 1.0
    for p, q in ((-dx, a[0] - west), (dx, east - a[0]), (-dy, a[1] - south), (dy, north - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        ratio = q / p
        if p < 0:
            low = max(low, ratio)
        else:
            high = min(high, ratio)
        if low > high:
            return False
    return True


def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    for a, b in zip(ring, ring[1:]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def _polygon_hits_box(polygon: list, box: tuple[float, float, float, float]) -> bool:
    west, south, east, north = box
    # A segment crossing the box includes both outer and hole boundaries.
    if any(_segment_hits_box(a, b, box) for ring in polygon for a, b in zip(ring, ring[1:])):
        return True
    # If the box is entirely inside the polygon, its corner lies inside the outer
    # ring and outside every hole. Polygon-inside-box was covered by segments.
    return bool(polygon and _in_ring(west, south, polygon[0])
                and not any(_in_ring(west, south, ring) for ring in polygon[1:]))


def geometry_intersects_bbox(geometry: dict | None, bbox: tuple[float, float, float, float]) -> bool:
    """Intersect validated FRA polygons with a query box; split a dateline-crossing box."""
    if not isinstance(geometry, dict):
        return False
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        return False
    if geometry.get("type") == "Polygon":
        polygons = [coordinates]
    elif geometry.get("type") == "MultiPolygon":
        polygons = coordinates
    else:
        return False
    west, south, east, north = bbox
    boxes = [(west, south, east, north)] if west <= east else [
        (west, south, 180.0, north), (-180.0, south, east, north),
    ]
    return any(_polygon_hits_box(polygon, box) for box in boxes for polygon in polygons)
