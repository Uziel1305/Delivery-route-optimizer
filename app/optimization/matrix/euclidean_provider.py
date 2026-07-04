from __future__ import annotations

import math

from app.optimization.matrix.base import TimeMatrixProvider
from app.optimization.matrix.points import build_points
from app.optimization.models import Courier, Stop, TimeMatrix

EARTH_RADIUS_METERS = 6_371_000


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


class EuclideanTimeMatrixProvider(TimeMatrixProvider):
    """Straight-line-distance-based provider for benchmarking synthetic instances.

    Not for production routing — no road network awareness.
    """

    def __init__(self, average_speed_mps: float = 12.0):
        self.average_speed_mps = average_speed_mps

    def get_matrix(self, couriers: tuple[Courier, ...], stops: tuple[Stop, ...]) -> TimeMatrix:
        point_ids, coordinates = build_points(couriers, stops)
        n = len(coordinates)
        rows: list[tuple[float, ...]] = []
        for i in range(n):
            row = []
            for j in range(n):
                if i == j:
                    row.append(0.0)
                else:
                    meters = _haversine_meters(
                        coordinates[i].lat, coordinates[i].lon, coordinates[j].lat, coordinates[j].lon
                    )
                    row.append(meters / self.average_speed_mps)
            rows.append(tuple(row))

        return TimeMatrix(matrix=tuple(rows), point_ids=point_ids)
