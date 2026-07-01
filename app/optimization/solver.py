"""Orchestration layer. Only this module (plus the Celery task and API) may
call registry.get_algorithm() / default_algorithm_for_tier() — concrete
algorithm classes are never imported directly from outside app/optimization.
"""
from __future__ import annotations

import itertools

from app.optimization import registry
from app.optimization.algorithms.exact_dp import held_karp_single_route, prepare_shared_tables, solve_for_couriers
from app.optimization.config import DEFAULT_CONFIG
from app.optimization.models import (
    AlgorithmTier,
    Courier,
    CourierRoute,
    Depot,
    ProblemInstance,
    RouteLeg,
    SolutionResult,
    Stop,
    TimeMatrix,
)

EPSILON = 1e-9


def select_tier(instance: ProblemInstance) -> AlgorithmTier:
    if len(instance.stops) <= DEFAULT_CONFIG.optimal_tier_max_stops:
        return AlgorithmTier.OPTIMAL
    return AlgorithmTier.HEURISTIC


def solve(
    instance: ProblemInstance, *, time_budget_seconds: float | None = None
) -> SolutionResult:
    """Default entry point: auto-select tier by stop count, run that tier's
    default algorithm against the full courier pool. There is no user-facing
    algorithm picker — tier selection is internal.
    """
    tier = select_tier(instance)
    algorithm = registry.default_algorithm_for_tier(tier)
    budget = (
        time_budget_seconds
        if time_budget_seconds is not None
        else DEFAULT_CONFIG.default_time_budget_seconds
    )
    return algorithm.solve(instance, time_budget_seconds=budget)


def solve_with_courier_count(
    instance: ProblemInstance,
    target_courier_count: int,
    *,
    time_budget_seconds: float | None = None,
) -> SolutionResult | None:
    """Try to serve every stop using exactly `target_courier_count` couriers
    drawn from instance.couriers. Returns None if infeasible for that count —
    callers (the "try with N couriers" endpoint) must leave all existing
    options untouched on None.
    """
    couriers = instance.couriers
    m = len(couriers)
    n = target_courier_count

    if n <= 0 or n > m:
        return None

    tier = select_tier(instance)

    if tier == AlgorithmTier.OPTIMAL:
        # Phase 1's route_cost table only depends on the stop set, not on
        # which couriers are chosen — compute it once, reuse across every
        # C(M, N) subset instead of re-running Held-Karp per subset.
        shared = prepare_shared_tables(instance)
        best_result: SolutionResult | None = None
        for subset in itertools.combinations(couriers, n):
            result = solve_for_couriers(instance, subset, shared)
            if result is None:
                continue
            if best_result is None or result.total_duration_seconds < best_result.total_duration_seconds:
                best_result = result
        return best_result

    return _heuristic_solve_with_courier_count(instance, n, time_budget_seconds)


def _heuristic_solve_with_courier_count(
    instance: ProblemInstance,
    target_courier_count: int,
    time_budget_seconds: float | None,
) -> SolutionResult | None:
    """Deterministic greedy courier-dropping: repeatedly drop the
    currently-lightest-loaded courier and re-solve with the remaining pool,
    until exactly target_courier_count remain. Chosen over randomized subset
    sampling for determinism/explainability/testability.
    """
    algorithm = registry.get_algorithm(DEFAULT_CONFIG.default_algorithm_key[AlgorithmTier.HEURISTIC])
    remaining_couriers = list(instance.couriers)

    while len(remaining_couriers) > target_courier_count:
        trial_instance = ProblemInstance(
            depot=instance.depot,
            stops=instance.stops,
            couriers=tuple(remaining_couriers),
            time_matrix=instance.time_matrix,
        )
        result = algorithm.solve(trial_instance, time_budget_seconds=time_budget_seconds)
        if not result.feasible:
            return None

        duration_by_courier_id = {r.courier_id: r.total_duration_seconds for r in result.routes}
        lightest = min(remaining_couriers, key=lambda c: duration_by_courier_id.get(c.id, 0.0))
        remaining_couriers = [c for c in remaining_couriers if c.id != lightest.id]

    final_instance = ProblemInstance(
        depot=instance.depot,
        stops=instance.stops,
        couriers=tuple(remaining_couriers),
        time_matrix=instance.time_matrix,
    )
    final_result = algorithm.solve(final_instance, time_budget_seconds=time_budget_seconds)
    if not final_result.feasible:
        return None
    return final_result


def reorder_single_route(
    courier: Courier,
    stops: tuple[Stop, ...],
    depot: Depot,
    time_matrix: TimeMatrix,
) -> CourierRoute | None:
    """Recompute the optimal stop order for one courier's already-decided
    stop list (used by the manager "swap" flow — a swap only ever moves
    which courier a stop belongs to, never manually reorders within a
    route). Returns None if no ordering fits the courier's window.
    """
    if len(stops) <= DEFAULT_CONFIG.optimal_tier_max_stops:
        return held_karp_single_route(stops, depot, courier.id, courier.window_seconds, time_matrix)
    return _nearest_neighbor_2opt_single_route(courier, stops, time_matrix)


def _nearest_neighbor_2opt_single_route(
    courier: Courier, stops: tuple[Stop, ...], time_matrix: TimeMatrix
) -> CourierRoute | None:
    stop_index_by_id = {sid: i + 1 for i, sid in enumerate(time_matrix.stop_ids)}
    matrix_idx = {s.id: stop_index_by_id[s.id] for s in stops}
    dist = time_matrix.matrix

    remaining = list(stops)
    order: list[Stop] = []
    current = 0  # depot
    while remaining:
        nxt = min(remaining, key=lambda s: dist[current][matrix_idx[s.id]])
        order.append(nxt)
        current = matrix_idx[nxt.id]
        remaining.remove(nxt)

    def route_travel(seq: list[Stop]) -> float:
        if not seq:
            return 0.0
        total = dist[0][matrix_idx[seq[0].id]]
        for a, b in zip(seq, seq[1:]):
            total += dist[matrix_idx[a.id]][matrix_idx[b.id]]
        total += dist[matrix_idx[seq[-1].id]][0]
        return total

    improved = True
    while improved:
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                candidate = order[:i] + order[i : j + 1][::-1] + order[j + 1 :]
                if route_travel(candidate) < route_travel(order) - EPSILON:
                    order = candidate
                    improved = True

    total_service = sum(s.service_time_seconds for s in order)
    total_travel = route_travel(order)
    if total_travel + total_service > courier.window_seconds:
        return None

    legs: list[RouteLeg] = []
    prev_idx = 0
    prev_id: str | None = None
    for s in order:
        idx = matrix_idx[s.id]
        legs.append(RouteLeg(from_stop_id=prev_id, to_stop_id=s.id, travel_seconds=dist[prev_idx][idx]))
        prev_idx = idx
        prev_id = s.id
    if order:
        legs.append(RouteLeg(from_stop_id=prev_id, to_stop_id=None, travel_seconds=dist[prev_idx][0]))

    return CourierRoute(
        courier_id=courier.id,
        ordered_stop_ids=tuple(s.id for s in order),
        legs=tuple(legs),
        total_travel_seconds=total_travel,
        total_service_seconds=total_service,
    )
