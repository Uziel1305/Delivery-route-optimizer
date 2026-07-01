from __future__ import annotations

import httpx

from app.optimization.exceptions import OptimizationError
from app.optimization.matrix.base import TimeMatrixProvider
from app.optimization.models import Depot, Stop, TimeMatrix


class OsrmMatrixError(OptimizationError):
    """Raised when OSRM returns an unusable table (e.g. unreachable point)."""


class OsrmTimeMatrixProvider(TimeMatrixProvider):
    """Calls a self-hosted OSRM /table endpoint for real travel-time data.

    NOTE: OSRM expects coordinates as "lon,lat" — the opposite order of the
    Coordinate(lat, lon) dataclass used everywhere else in this package.
    """

    def __init__(self, base_url: str, timeout_seconds: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_matrix(self, depot: Depot, stops: tuple[Stop, ...]) -> TimeMatrix:
        points = [depot.coordinate] + [s.coordinate for s in stops]
        coords_param = ";".join(f"{p.lon},{p.lat}" for p in points)
        url = f"{self.base_url}/table/v1/driving/{coords_param}"

        response = httpx.get(
            url,
            params={"annotations": "duration"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("code") != "Ok":
            raise OsrmMatrixError(f"OSRM returned non-Ok code: {payload.get('code')}")

        durations = payload["durations"]
        for row in durations:
            if any(cell is None for cell in row):
                raise OsrmMatrixError(
                    "OSRM returned a null duration entry — a point may be unreachable "
                    "from the road network."
                )

        matrix = tuple(tuple(float(cell) for cell in row) for row in durations)
        return TimeMatrix(matrix=matrix, stop_ids=tuple(s.id for s in stops))
