from __future__ import annotations

from abc import ABC, abstractmethod

from app.optimization.models import (
    AlgorithmTier,
    CourierRoute,
    ProblemInstance,
    RouteLeg,
    SolutionResult,
)


class RoutingAlgorithm(ABC):
    key: str
    display_name: str
    tier: AlgorithmTier

    @abstractmethod
    def solve(
        self,
        instance: ProblemInstance,
        *,
        time_budget_seconds: float | None = None,
        seed: int | None = None,
    ) -> SolutionResult:
        ...

    def supports(self, instance: ProblemInstance) -> bool:
        return True


class RoutingAlgorithmBase(RoutingAlgorithm):
    """Shared helpers for concrete algorithm implementations."""

    def _route_from_order(
        self,
        courier_id: str,
        ordered_stop_ids: tuple[str, ...],
        stop_index_by_id: dict[str, int],
        service_time_by_stop_id: dict[str, int],
        time_matrix,
    ) -> CourierRoute:
        legs: list[RouteLeg] = []
        total_travel = 0.0
        total_service = 0.0

        prev_index = 0  # depot
        prev_stop_id: str | None = None
        for stop_id in ordered_stop_ids:
            idx = stop_index_by_id[stop_id]
            travel = time_matrix.travel_seconds(prev_index, idx)
            legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=stop_id, travel_seconds=travel))
            total_travel += travel
            total_service += service_time_by_stop_id[stop_id]
            prev_index = idx
            prev_stop_id = stop_id

        if ordered_stop_ids:
            travel_back = time_matrix.travel_seconds(prev_index, 0)
            legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=None, travel_seconds=travel_back))
            total_travel += travel_back

        return CourierRoute(
            courier_id=courier_id,
            ordered_stop_ids=ordered_stop_ids,
            legs=tuple(legs),
            total_travel_seconds=total_travel,
            total_service_seconds=total_service,
        )
