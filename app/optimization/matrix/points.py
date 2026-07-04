"""Shared helper: the canonical point ordering every provider must use —
each courier's start and end terminal (in courier order), then all stops.
"""
from __future__ import annotations

from app.optimization.models import Coordinate, Courier, Stop, end_point_id, start_point_id


def build_points(
    couriers: tuple[Courier, ...], stops: tuple[Stop, ...]
) -> tuple[tuple[str, ...], tuple[Coordinate, ...]]:
    point_ids: list[str] = []
    coordinates: list[Coordinate] = []
    for c in couriers:
        point_ids.append(start_point_id(c.id))
        coordinates.append(c.start)
        point_ids.append(end_point_id(c.id))
        coordinates.append(c.end)
    for s in stops:
        point_ids.append(s.id)
        coordinates.append(s.coordinate)
    return tuple(point_ids), tuple(coordinates)
