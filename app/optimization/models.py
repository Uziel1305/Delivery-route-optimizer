"""Framework-agnostic data model for the routing/optimization package.

No FastAPI, SQLAlchemy, or Celery imports allowed in this package — see
app/services/optimization_adapter.py for the mapping boundary to the ORM.

Multi-terminal model: there is no shared depot. Every courier has their own
start and end coordinate (which may differ), and a route runs
courier start -> stops -> courier end. A courier assigned no stops drives
nothing and costs zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
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


def start_point_id(courier_id: str) -> str:
    """Synthetic TimeMatrix point id for a courier's start location."""
    return f"start:{courier_id}"


def end_point_id(courier_id: str) -> str:
    """Synthetic TimeMatrix point id for a courier's end location."""
    return f"end:{courier_id}"


@dataclass(frozen=True)
class Courier:
    id: str
    start_time_seconds: int
    end_time_seconds: int
    start: Coordinate
    end: Coordinate

    @property
    def window_seconds(self) -> int:
        return self.end_time_seconds - self.start_time_seconds


@dataclass(frozen=True)
class TimeMatrix:
    """Square matrix of travel seconds over labeled points.

    point_ids[i] names row/col i. Points are stop ids plus the synthetic
    courier-terminal ids produced by start_point_id()/end_point_id().
    """
    matrix: tuple[tuple[float, ...], ...]
    point_ids: tuple[str, ...]

    @cached_property
    def _index_by_point_id(self) -> dict[str, int]:
        return {pid: i for i, pid in enumerate(self.point_ids)}

    def index_of(self, point_id: str) -> int:
        return self._index_by_point_id[point_id]

    def start_index(self, courier_id: str) -> int:
        return self.index_of(start_point_id(courier_id))

    def end_index(self, courier_id: str) -> int:
        return self.index_of(end_point_id(courier_id))

    def stop_index(self, stop_id: str) -> int:
        return self.index_of(stop_id)

    def travel_seconds(self, from_index: int, to_index: int) -> float:
        return self.matrix[from_index][to_index]

    @property
    def size(self) -> int:
        return len(self.matrix)


@dataclass(frozen=True)
class ProblemInstance:
    stops: tuple[Stop, ...]
    couriers: tuple[Courier, ...]
    time_matrix: TimeMatrix


@dataclass(frozen=True)
class RouteLeg:
    from_stop_id: str | None  # None means "from the courier's start location"
    to_stop_id: str | None    # None means "to the courier's end location"
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
