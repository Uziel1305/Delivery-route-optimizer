from __future__ import annotations

import random

from app.optimization.matrix.euclidean_provider import EuclideanTimeMatrixProvider
from app.optimization.models import Coordinate, Courier, Depot, ProblemInstance, Stop

# Roughly a Tel Aviv metro-area bounding box — realistic-scale coordinates
# for the euclidean provider without needing real map data.
LAT_RANGE = (32.00, 32.20)
LON_RANGE = (34.75, 34.95)


def generate_synthetic_instance(
    n_stops: int,
    n_couriers: int,
    *,
    seed: int | None = None,
    courier_window_seconds: int = 8 * 3600,
    service_time_seconds: int = 120,
) -> ProblemInstance:
    rng = random.Random(seed)

    depot = Depot(coordinate=Coordinate(lat=32.08, lon=34.78))

    stops = tuple(
        Stop(
            id=f"stop-{i}",
            coordinate=Coordinate(
                lat=rng.uniform(*LAT_RANGE),
                lon=rng.uniform(*LON_RANGE),
            ),
            service_time_seconds=service_time_seconds,
        )
        for i in range(n_stops)
    )

    couriers = tuple(
        Courier(id=f"courier-{c}", start_time_seconds=0, end_time_seconds=courier_window_seconds)
        for c in range(n_couriers)
    )

    matrix_provider = EuclideanTimeMatrixProvider()
    time_matrix = matrix_provider.get_matrix(depot, stops)

    return ProblemInstance(depot=depot, stops=stops, couriers=couriers, time_matrix=time_matrix)
