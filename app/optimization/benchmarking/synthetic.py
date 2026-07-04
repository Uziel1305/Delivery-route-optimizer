from __future__ import annotations

import random

from app.optimization.matrix.euclidean_provider import EuclideanTimeMatrixProvider
from app.optimization.models import Coordinate, Courier, ProblemInstance, Stop

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

    def random_coordinate() -> Coordinate:
        return Coordinate(lat=rng.uniform(*LAT_RANGE), lon=rng.uniform(*LON_RANGE))

    stops = tuple(
        Stop(
            id=f"stop-{i}",
            coordinate=random_coordinate(),
            service_time_seconds=service_time_seconds,
        )
        for i in range(n_stops)
    )

    # Each courier gets their own (usually distinct) start and end terminals,
    # exercising the multi-terminal model in every property test.
    couriers = tuple(
        Courier(
            id=f"courier-{c}",
            start_time_seconds=0,
            end_time_seconds=courier_window_seconds,
            start=random_coordinate(),
            end=random_coordinate(),
        )
        for c in range(n_couriers)
    )

    matrix_provider = EuclideanTimeMatrixProvider()
    time_matrix = matrix_provider.get_matrix(couriers, stops)

    return ProblemInstance(stops=stops, couriers=couriers, time_matrix=time_matrix)
