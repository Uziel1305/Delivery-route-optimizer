"""OPTIMAL tier: per-courier Held-Karp DP (Phase 1) feeding a set-partition DP
over couriers (Phase 2).

Every courier has their own start/end terminals, so Phase 1 computes
route_cost[courier][S] — the optimal start -> S -> end path cost for every
subset S of stops, once per courier — in O(k * n^2 * 2^n). (With a shared
depot this table used to be courier-independent; per-courier terminals make
that impossible.)

Phase 2 partitions the full stop set across couriers using those lookup
tables: best[c][S] = min cost to cover exactly S using the first c couriers,
subject to each courier's time window. O(3^n * k). A courier assigned no
stops drives nothing and costs zero.

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
    Courier,
    CourierRoute,
    ProblemInstance,
    RouteLeg,
    SolutionResult,
    Stop,
    TimeMatrix,
)
from app.optimization.registry import register_algorithm

INF = math.inf


def _build_local_matrix(
    courier: Courier, stops: tuple[Stop, ...], time_matrix: TimeMatrix
) -> list[list[float]]:
    """Reindex the global TimeMatrix to a local (n+2)x(n+2) matrix where
    local index 0 is the courier's start, i+1 is stops[i], and n+1 is the
    courier's end.
    """
    global_indices = (
        [time_matrix.start_index(courier.id)]
        + [time_matrix.stop_index(s.id) for s in stops]
        + [time_matrix.end_index(courier.id)]
    )
    size = len(global_indices)
    return [
        [time_matrix.matrix[global_indices[a]][global_indices[b]] for b in range(size)]
        for a in range(size)
    ]


def _compute_route_cost_table(
    n: int, dist_local: list[list[float]]
) -> tuple[list[float], list[list[float]], list[list[int]], list[int]]:
    """Held-Karp over all n stops for one courier's local matrix.
    Returns (route_cost, dp, parent, best_last_for_mask).

    dp[mask][j] = min travel cost of a start-anchored path visiting exactly
    the local stops in `mask`, ending at local stop j.
    route_cost[mask] = optimal start -> mask -> end travel cost for that
    subset (0.0 for the empty subset — an idle courier drives nothing).
    """
    size = 1 << n
    end_local = n + 1
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
            cost = dp[mask][j] + dist_local[j + 1][end_local]
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


def _route_from_local_order(
    courier_id: str,
    order_local: list[int],
    stops: tuple[Stop, ...],
    dist_local: list[list[float]],
) -> CourierRoute:
    """Build a CourierRoute from a local stop order against one courier's
    local matrix (0 = start, n+1 = end). Empty order = idle courier: no legs.
    """
    if not order_local:
        return CourierRoute(
            courier_id=courier_id,
            ordered_stop_ids=(),
            legs=(),
            total_travel_seconds=0.0,
            total_service_seconds=0.0,
        )

    end_local = len(stops) + 1
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
    travel_out = dist_local[prev_a][end_local]
    legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=None, travel_seconds=travel_out))
    travel_total += travel_out

    service_total = sum(stops[i].service_time_seconds for i in order_local)
    return CourierRoute(
        courier_id=courier_id,
        ordered_stop_ids=tuple(stops[i].id for i in order_local),
        legs=tuple(legs),
        total_travel_seconds=travel_total,
        total_service_seconds=service_total,
    )


def _set_partition_dp(
    n: int,
    k: int,
    route_costs: list[list[float]],
    service_sum: list[float],
    windows: list[int],
) -> tuple[list[list[float]], list[list[int]]]:
    """best[c][S] = min total (travel+service) cost to cover exactly S using
    the first c couriers (in the order given), with courier c-1's own
    route_costs table. choice[c][S] = the subset assigned to courier c-1
    achieving that optimum, for reconstruction.
    """
    size = 1 << n
    best = [[INF] * size for _ in range(k + 1)]
    choice = [[-1] * size for _ in range(k + 1)]
    best[0][0] = 0.0

    for c in range(1, k + 1):
        window = windows[c - 1]
        route_cost = route_costs[c - 1]
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
    courier: Courier,
    time_matrix: TimeMatrix,
) -> CourierRoute | None:
    """Optimal ordering of exactly `stops` for one courier, from their start
    terminal to their end terminal.

    Returns None if no ordering fits within the courier's window (travel +
    service combined). Used by solver.reorder_single_route() after a manager
    swaps a stop between couriers — a single-subset exact solve, distinct
    from the whole-instance route_cost tables above.
    """
    n = len(stops)
    total_service = sum(s.service_time_seconds for s in stops)

    if n == 0:
        return CourierRoute(
            courier_id=courier.id,
            ordered_stop_ids=(),
            legs=(),
            total_travel_seconds=0.0,
            total_service_seconds=0.0,
        )

    dist_local = _build_local_matrix(courier, stops, time_matrix)
    route_cost, dp, parent, best_last_for_mask = _compute_route_cost_table(n, dist_local)

    full_mask = (1 << n) - 1
    best_travel = route_cost[full_mask]
    if best_travel == INF or best_travel + total_service > courier.window_seconds:
        return None

    order_local = _reconstruct_order(full_mask, dp, parent, best_last_for_mask)
    return _route_from_local_order(courier.id, order_local, stops, dist_local)


class _CourierTables:
    """Phase-1 results for one courier against the instance's stop set."""

    __slots__ = ("dist_local", "route_cost", "dp", "parent", "best_last_for_mask")

    def __init__(self, courier: Courier, stops: tuple[Stop, ...], time_matrix: TimeMatrix, n: int):
        self.dist_local = _build_local_matrix(courier, stops, time_matrix)
        self.route_cost, self.dp, self.parent, self.best_last_for_mask = _compute_route_cost_table(
            n, self.dist_local
        )


class SharedTables:
    """Phase-1 results for every courier in the instance. Computed once per
    generation and reused across every courier-subset evaluated by
    solve_for_couriers() (e.g. "try with N couriers" enumerating C(M,N)
    subsets — each courier's table is courier-specific but subset-independent).
    """

    __slots__ = ("n", "service_times", "service_sum", "by_courier_id")

    def __init__(self, instance: ProblemInstance):
        stops = instance.stops
        self.n = len(stops)
        self.service_times = [s.service_time_seconds for s in stops]
        self.service_sum = _service_sum_table(self.n, self.service_times)
        self.by_courier_id = {
            c.id: _CourierTables(c, stops, instance.time_matrix, self.n) for c in instance.couriers
        }


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
    tables = [shared.by_courier_id[c.id] for c in couriers]
    route_costs = [t.route_cost for t in tables]
    full_mask = (1 << n) - 1

    best, choice = _set_partition_dp(n, k, route_costs, shared.service_sum, windows)
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
        ct = tables[idx]
        order_local = _reconstruct_order(mask, ct.dp, ct.parent, ct.best_last_for_mask)
        routes.append(_route_from_local_order(courier.id, order_local, stops, ct.dist_local))

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
