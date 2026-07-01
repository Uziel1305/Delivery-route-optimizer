"""Framework-agnostic data model for the routing/optimization package.

No FastAPI, SQLAlchemy, or Celery imports allowed in this package — see
app/services/optimization_adapter.py for the mapping boundary to the ORM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float


@dataclass(frozen=True)
class Stop:
    id: str
    coordinate: Coordinate
    service_time_seconds: int = 0


@dataclass(frozen=True)
class Depot:
    coordinate: Coordinate


@dataclass(frozen=True)
class Courier:
    id: str
    start_time_seconds: int
    end_time_seconds: int

    @property
    def window_seconds(self) -> int:
        return self.end_time_seconds - self.start_time_seconds


@dataclass(frozen=True)
class TimeMatrix:
    """Square matrix of travel seconds. Index 0 is always the depot.

    stop_ids[i - 1] gives the Stop.id for matrix row/col i (i >= 1).
    """
    matrix: tuple[tuple[float, ...], ...]
    stop_ids: tuple[str, ...]

    def travel_seconds(self, from_index: int, to_index: int) -> float:
        return self.matrix[from_index][to_index]

    @property
    def size(self) -> int:
        return len(self.matrix)


@dataclass(frozen=True)
class ProblemInstance:
    depot: Depot
    stops: tuple[Stop, ...]
    couriers: tuple[Courier, ...]
    time_matrix: TimeMatrix


@dataclass(frozen=True)
class RouteLeg:
    from_stop_id: str | None  # None means "from depot"
    to_stop_id: str | None    # None means "to depot"
    travel_seconds: float


@dataclass(frozen=True)
class CourierRoute:
    courier_id: str
    ordered_stop_ids: tuple[str, ...]
    legs: tuple[RouteLeg, ...]
    total_travel_seconds: float
    total_service_seconds: float

    @property
    def total_duration_seconds(self) -> float:
        return self.total_travel_seconds + self.total_service_seconds


class AlgorithmTier(str, Enum):
    OPTIMAL = "optimal"
    HEURISTIC = "heuristic"
    EXPERIMENTAL = "experimental"


@dataclass(frozen=True)
class SolutionResult:
    routes: tuple[CourierRoute, ...]
    unassigned_stop_ids: tuple[str, ...]
    total_duration_seconds: float
    algorithm_key: str
    algorithm_tier: AlgorithmTier
    feasible: bool
    metadata: dict[str, Any] = field(default_factory=dict)
