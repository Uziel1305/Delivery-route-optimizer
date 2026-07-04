from __future__ import annotations

from abc import ABC, abstractmethod

from app.optimization.models import (
    AlgorithmTier,
    Courier,
    CourierRoute,
    ProblemInstance,
    RouteLeg,
    SolutionResult,
    TimeMatrix,
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
        courier: Courier,
        ordered_stop_ids: tuple[str, ...],
        service_time_by_stop_id: dict[str, int],
        time_matrix: TimeMatrix,
    ) -> CourierRoute:
        if not ordered_stop_ids:
            return CourierRoute(
                courier_id=courier.id,
                ordered_stop_ids=(),
                legs=(),
                total_travel_seconds=0.0,
                total_service_seconds=0.0,
            )

        legs: list[RouteLeg] = []
        total_travel = 0.0
        total_service = 0.0

        prev_index = time_matrix.start_index(courier.id)
        prev_stop_id: str | None = None
        for stop_id in ordered_stop_ids:
            idx = time_matrix.stop_index(stop_id)
            travel = time_matrix.travel_seconds(prev_index, idx)
            legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=stop_id, travel_seconds=travel))
            total_travel += travel
            total_service += service_time_by_stop_id[stop_id]
            prev_index = idx
            prev_stop_id = stop_id

        travel_out = time_matrix.travel_seconds(prev_index, time_matrix.end_index(courier.id))
        legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=None, travel_seconds=travel_out))
        total_travel += travel_out

        return CourierRoute(
            courier_id=courier.id,
            ordered_stop_ids=ordered_stop_ids,
            legs=tuple(legs),
            total_travel_seconds=total_travel,
            total_service_seconds=total_service,
        )
