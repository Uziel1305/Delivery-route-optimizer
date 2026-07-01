"""OPTIMAL tier: a shared Held-Karp DP (Phase 1) feeding a set-partition DP
over couriers (Phase 2).

Phase 1 computes route_cost[S] — the optimal single-vehicle round-trip travel
cost for every possible subset S of stops — in a single O(n^2 * 2^n) pass,
rather than re-running Held-Karp once per courier-subset.

Phase 2 partitions the full stop set across couriers using that lookup table:
best[c][S] = min cost to cover exactly S using the first c couriers, subject
to each courier's time window. O(3^n * k).

See held_karp_single_route() for the separate, simpler exact solver used by
solver.reorder_single_route() to reorder one courier's already-decided stop
list (not to be confused with the whole-instance DP above).
"""
from __future__ import annotations

import math

from app.optimization.base import RoutingAlgorithmBase
from app.optimization.config import DEFAULT_CONFIG
from app.optimization.models import (
    AlgorithmTier,
    CourierRoute,
    Depot,
    ProblemInstance,
    RouteLeg,
    SolutionResult,
    Stop,
    TimeMatrix,
)
from app.optimization.registry import register_algorithm

INF = math.inf


def _build_local_matrix(
    stops: tuple[Stop, ...], time_matrix: TimeMatrix
) -> list[list[float]]:
    """Reindex the global TimeMatrix to a local (n+1)x(n+1) matrix where
    local index 0 is the depot and local index i+1 is stops[i].
    """
    stop_index_by_id = {sid: i + 1 for i, sid in enumerate(time_matrix.stop_ids)}
    global_indices = [0] + [stop_index_by_id[s.id] for s in stops]
    size = len(global_indices)
    return [
        [time_matrix.matrix[global_indices[a]][global_indices[b]] for b in range(size)]
        for a in range(size)
    ]


def _compute_route_cost_table(
    n: int, dist_local: list[list[float]]
) -> tuple[list[float], list[list[float]], list[list[int]], list[int]]:
    """Held-Karp over all n stops. Returns (route_cost, dp, parent, best_last_for_mask).

    dp[mask][j] = min travel cost of a depot-started path visiting exactly
    the local stops in `mask`, ending at local stop j.
    route_cost[mask] = optimal depot round-trip travel cost for that subset.
    """
    size = 1 << n
    dp = [[INF] * n for _ in range(size)]
    parent = [[-1] * n for _ in range(size)]

    for j in range(n):
        dp[1 << j][j] = dist_local[0][j + 1]

    for mask in range(size):
        for j in range(n):
            if not (mask & (1 << j)):
                continue
            cur = dp[mask][j]
            if cur == INF:
                continue
            for k in range(n):
                if mask & (1 << k):
                    continue
                new_mask = mask | (1 << k)
                cost = cur + dist_local[j + 1][k + 1]
                if cost < dp[new_mask][k]:
                    dp[new_mask][k] = cost
                    parent[new_mask][k] = j

    route_cost = [INF] * size
    best_last_for_mask = [-1] * size
    route_cost[0] = 0.0
    for mask in range(1, size):
        best_cost = INF
        best_j = -1
        for j in range(n):
            if not (mask & (1 << j)) or dp[mask][j] == INF:
                continue
            cost = dp[mask][j] + dist_local[j + 1][0]
            if cost < best_cost:
                best_cost = cost
                best_j = j
        route_cost[mask] = best_cost
        best_last_for_mask[mask] = best_j

    return route_cost, dp, parent, best_last_for_mask


def _service_sum_table(n: int, service_times: list[int]) -> list[float]:
    size = 1 << n
    service_sum = [0.0] * size
    for mask in range(1, size):
        lowest = mask & (-mask)
        lowest_idx = lowest.bit_length() - 1
        service_sum[mask] = service_sum[mask ^ lowest] + service_times[lowest_idx]
    return service_sum


def _reconstruct_order(
    mask: int,
    dp: list[list[float]],
    parent: list[list[int]],
    best_last_for_mask: list[int],
) -> list[int]:
    j = best_last_for_mask[mask]
    if j == -1:
        return []
    order: list[int] = []
    m = mask
    while j != -1:
        order.append(j)
        prev_j = parent[m][j]
        m ^= 1 << j
        j = prev_j
    order.reverse()
    return order


def _set_partition_dp(
    n: int,
    k: int,
    route_cost: list[float],
    service_sum: list[float],
    windows: list[int],
) -> tuple[list[list[float]], list[list[int]]]:
    """best[c][S] = min total (travel+service) cost to cover exactly S using
    the first c couriers (in the order given). choice[c][S] = the subset
    assigned to courier c-1 achieving that optimum, for reconstruction.
    """
    size = 1 << n
    best = [[INF] * size for _ in range(k + 1)]
    choice = [[-1] * size for _ in range(k + 1)]
    best[0][0] = 0.0

    for c in range(1, k + 1):
        window = windows[c - 1]
        prev_best = best[c - 1]
        for s in range(size):
            best_val = INF
            best_t = -1
            t = s
            while True:
                cost_t = route_cost[t] + service_sum[t]
                fits = t == 0 or cost_t <= window
                if fits and prev_best[s ^ t] < INF:
                    val = prev_best[s ^ t] + (cost_t if t != 0 else 0.0)
                    if val < best_val:
                        best_val = val
                        best_t = t
                if t == 0:
                    break
                t = (t - 1) & s
            best[c][s] = best_val
            choice[c][s] = best_t

    return best, choice


def held_karp_single_route(
    stops: tuple[Stop, ...],
    depot: Depot,
    courier_id: str,
    window_seconds: int,
    time_matrix: TimeMatrix,
) -> CourierRoute | None:
    """Optimal ordering of exactly `stops` for one vehicle.

    Returns None if no ordering fits within `window_seconds` (travel + service
    combined). Used by solver.reorder_single_route() after a manager swaps a
    stop between couriers — a single-subset exact solve, distinct from the
    whole-instance route_cost table above.
    """
    n = len(stops)
    total_service = sum(s.service_time_seconds for s in stops)

    if n == 0:
        if total_service > window_seconds:
            return None
        return CourierRoute(
            courier_id=courier_id,
            ordered_stop_ids=(),
            legs=(),
            total_travel_seconds=0.0,
            total_service_seconds=0.0,
        )

    dist_local = _build_local_matrix(stops, time_matrix)
    route_cost, dp, parent, best_last_for_mask = _compute_route_cost_table(n, dist_local)

    full_mask = (1 << n) - 1
    best_travel = route_cost[full_mask]
    if best_travel == INF or best_travel + total_service > window_seconds:
        return None

    order_local = _reconstruct_order(full_mask, dp, parent, best_last_for_mask)
    ordered_stop_ids = tuple(stops[i].id for i in order_local)

    legs: list[RouteLeg] = []
    prev_a = 0
    prev_stop_id: str | None = None
    travel_total = 0.0
    for i in order_local:
        a = i + 1
        travel = dist_local[prev_a][a]
        legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=stops[i].id, travel_seconds=travel))
        travel_total += travel
        prev_a = a
        prev_stop_id = stops[i].id
    travel_back = dist_local[prev_a][0]
    legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=None, travel_seconds=travel_back))
    travel_total += travel_back

    return CourierRoute(
        courier_id=courier_id,
        ordered_stop_ids=ordered_stop_ids,
        legs=tuple(legs),
        total_travel_seconds=travel_total,
        total_service_seconds=total_service,
    )


class SharedTables:
    """Phase-1 results for one instance's stop set — independent of which
    couriers are used. Computed once per generation and reused across every
    courier-subset evaluated by solve_for_couriers() (e.g. "try with N
    couriers" enumerating C(M,N) subsets).
    """

    __slots__ = ("n", "dist_local", "route_cost", "dp", "parent", "best_last_for_mask", "service_times", "service_sum")

    def __init__(self, instance: ProblemInstance):
        stops = instance.stops
        self.n = len(stops)
        self.dist_local = _build_local_matrix(stops, instance.time_matrix)
        self.route_cost, self.dp, self.parent, self.best_last_for_mask = _compute_route_cost_table(
            self.n, self.dist_local
        )
        self.service_times = [s.service_time_seconds for s in stops]
        self.service_sum = _service_sum_table(self.n, self.service_times)


def prepare_shared_tables(instance: ProblemInstance) -> SharedTables:
    return SharedTables(instance)


def solve_for_couriers(
    instance: ProblemInstance,
    couriers: tuple,
    shared: SharedTables | None = None,
) -> SolutionResult | None:
    """Run Phase 2 (set-partition DP) + route reconstruction for a specific
    ordered subset of couriers, reusing precomputed Phase-1 tables.

    Returns None if this stop set cannot be fully covered by this courier
    subset within their windows (infeasible for this N/subset).
    """
    stops = instance.stops
    n = len(stops)
    k = len(couriers)

    if shared is None:
        shared = prepare_shared_tables(instance)

    if n == 0:
        routes = tuple(
            CourierRoute(
                courier_id=c.id,
                ordered_stop_ids=(),
                legs=(),
                total_travel_seconds=0.0,
                total_service_seconds=0.0,
            )
            for c in couriers
        )
        return SolutionResult(
            routes=routes,
            unassigned_stop_ids=(),
            total_duration_seconds=0.0,
            algorithm_key="held_karp_exact",
            algorithm_tier=AlgorithmTier.OPTIMAL,
            feasible=True,
        )

    if k == 0:
        return None

    windows = [c.window_seconds for c in couriers]
    full_mask = (1 << n) - 1

    best, choice = _set_partition_dp(n, k, shared.route_cost, shared.service_sum, windows)
    total_cost = best[k][full_mask]
    if total_cost == INF:
        return None

    masks_by_courier = [0] * k
    remaining = full_mask
    for c in range(k, 0, -1):
        t = choice[c][remaining]
        if t == -1:
            t = 0
        masks_by_courier[c - 1] = t
        remaining ^= t

    routes = []
    for idx, courier in enumerate(couriers):
        mask = masks_by_courier[idx]
        order_local = _reconstruct_order(mask, shared.dp, shared.parent, shared.best_last_for_mask)
        ordered_stop_ids = tuple(stops[i].id for i in order_local)

        legs: list[RouteLeg] = []
        prev_a = 0
        prev_stop_id: str | None = None
        travel_total = 0.0
        for i in order_local:
            a = i + 1
            travel = shared.dist_local[prev_a][a]
            legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=stops[i].id, travel_seconds=travel))
            travel_total += travel
            prev_a = a
            prev_stop_id = stops[i].id
        if order_local:
            travel_back = shared.dist_local[prev_a][0]
            legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=None, travel_seconds=travel_back))
            travel_total += travel_back

        service_total = sum(shared.service_times[i] for i in order_local)
        routes.append(
            CourierRoute(
                courier_id=courier.id,
                ordered_stop_ids=ordered_stop_ids,
                legs=tuple(legs),
                total_travel_seconds=travel_total,
                total_service_seconds=service_total,
            )
        )

    total_duration = sum(r.total_duration_seconds for r in routes)
    return SolutionResult(
        routes=tuple(routes),
        unassigned_stop_ids=(),
        total_duration_seconds=total_duration,
        algorithm_key="held_karp_exact",
        algorithm_tier=AlgorithmTier.OPTIMAL,
        feasible=True,
    )


@register_algorithm("held_karp_exact")
class HeldKarpExactAlgorithm(RoutingAlgorithmBase):
    display_name = "Held-Karp Exact (DP)"
    tier = AlgorithmTier.OPTIMAL

    def supports(self, instance: ProblemInstance) -> bool:
        return len(instance.stops) <= DEFAULT_CONFIG.optimal_tier_max_stops

    def solve(
        self,
        instance: ProblemInstance,
        *,
        time_budget_seconds: float | None = None,
        seed: int | None = None,
    ) -> SolutionResult:
        result = solve_for_couriers(instance, instance.couriers)
        if result is None:
            return SolutionResult(
                routes=(),
                unassigned_stop_ids=tuple(s.id for s in instance.stops),
                total_duration_seconds=0.0,
                algorithm_key=self.key,
                algorithm_tier=self.tier,
                feasible=False,
            )
        return result
