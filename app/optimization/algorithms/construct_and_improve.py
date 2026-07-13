"""HEURISTIC tier: parallel cheapest-insertion construction followed by
local search (intra-route 2-opt, cross-route Or-opt relocation, and
inter-route stop exchange) run to convergence — or until the
time_budget_seconds deadline, whichever comes first (anytime behavior:
expiry returns the best solution found so far, construction itself is
never budgeted).

Every route is anchored to its own courier's start/end terminals, so all
travel arithmetic is parameterized by courier index. An empty route costs
zero (an idle courier drives nothing).

Used for instances too large for the exact Held-Karp + set-partition DP in
exact_dp.py (see AlgorithmConfig.optimal_tier_max_stops).
"""
from __future__ import annotations

import time

from app.optimization.base import RoutingAlgorithmBase
from app.optimization.models import (
    AlgorithmTier,
    CourierRoute,
    ProblemInstance,
    RouteLeg,
    SolutionResult,
)
from app.optimization.registry import register_algorithm

EPSILON = 1e-9


def _expired(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() > deadline


class _RouteOps:
    """Bundles the travel/service arithmetic needed by construction and
    local search, closed over one instance's matrix, stop data, and each
    courier's terminal indices.
    """

    def __init__(self, instance: ProblemInstance):
        stops = instance.stops
        tm = instance.time_matrix

        self.stops = stops
        self.n = len(stops)
        self.dist = tm.matrix
        self.matrix_idx = [tm.stop_index(s.id) for s in stops]
        self.service_times = [s.service_time_seconds for s in stops]
        self.start_idx = [tm.start_index(c.id) for c in instance.couriers]
        self.end_idx = [tm.end_index(c.id) for c in instance.couriers]

    def travel(self, a: int, b: int) -> float:
        return self.dist[a][b]

    def route_travel_seconds(self, route: list[int], c: int) -> float:
        if not route:
            return 0.0
        total = self.travel(self.start_idx[c], self.matrix_idx[route[0]])
        for a, b in zip(route, route[1:]):
            total += self.travel(self.matrix_idx[a], self.matrix_idx[b])
        total += self.travel(self.matrix_idx[route[-1]], self.end_idx[c])
        return total

    def route_service_seconds(self, route: list[int]) -> float:
        return sum(self.service_times[i] for i in route)

    def route_duration_seconds(self, route: list[int], c: int) -> float:
        return self.route_travel_seconds(route, c) + self.route_service_seconds(route)

    def marginal_insertion_cost(self, route: list[int], position: int, stop_local_idx: int, c: int) -> float:
        s = self.matrix_idx[stop_local_idx]
        if not route:
            # An idle route's true cost is 0, so the first insertion pays the
            # full start -> stop -> end path (no "saved" start->end leg).
            return self.travel(self.start_idx[c], s) + self.travel(s, self.end_idx[c])
        prev = self.start_idx[c] if position == 0 else self.matrix_idx[route[position - 1]]
        nxt = self.end_idx[c] if position == len(route) else self.matrix_idx[route[position]]
        return self.travel(prev, s) + self.travel(s, nxt) - self.travel(prev, nxt)

    def to_courier_route(self, courier_id: str, route: list[int], c: int) -> CourierRoute:
        if not route:
            return CourierRoute(
                courier_id=courier_id,
                ordered_stop_ids=(),
                legs=(),
                total_travel_seconds=0.0,
                total_service_seconds=0.0,
            )
        legs: list[RouteLeg] = []
        prev_a = self.start_idx[c]
        prev_stop_id: str | None = None
        travel_total = 0.0
        for i in route:
            a = self.matrix_idx[i]
            travel = self.travel(prev_a, a)
            legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=self.stops[i].id, travel_seconds=travel))
            travel_total += travel
            prev_a = a
            prev_stop_id = self.stops[i].id
        travel_out = self.travel(prev_a, self.end_idx[c])
        legs.append(RouteLeg(from_stop_id=prev_stop_id, to_stop_id=None, travel_seconds=travel_out))
        travel_total += travel_out

        return CourierRoute(
            courier_id=courier_id,
            ordered_stop_ids=tuple(self.stops[i].id for i in route),
            legs=tuple(legs),
            total_travel_seconds=travel_total,
            total_service_seconds=self.route_service_seconds(route),
        )


def _construct_cheapest_insertion(
    ops: _RouteOps, k: int, windows: list[int]
) -> tuple[list[list[int]], set[int]]:
    routes: list[list[int]] = [[] for _ in range(k)]
    unplaced = set(range(ops.n))

    changed = True
    while unplaced and changed:
        changed = False
        best: tuple[float, int, int, int] | None = None  # (cost, stop_i, courier, position)

        for i in unplaced:
            for c in range(k):
                route = routes[c]
                for pos in range(len(route) + 1):
                    cost = ops.marginal_insertion_cost(route, pos, i, c)
                    candidate = route[:pos] + [i] + route[pos:]
                    if ops.route_duration_seconds(candidate, c) > windows[c]:
                        continue
                    if best is None or cost < best[0]:
                        best = (cost, i, c, pos)

        if best is not None:
            _, i, c, pos = best
            routes[c] = routes[c][:pos] + [i] + routes[c][pos:]
            unplaced.discard(i)
            changed = True

    return routes, unplaced


def _two_opt_pass(ops: _RouteOps, route: list[int], c: int, deadline: float | None = None) -> bool:
    improved_any = False
    improved = True
    while improved and not _expired(deadline):
        improved = False
        length = len(route)
        for i in range(length - 1):
            if _expired(deadline):
                return improved_any
            for j in range(i + 1, length):
                candidate = route[:i] + route[i : j + 1][::-1] + route[j + 1 :]
                if ops.route_travel_seconds(candidate, c) < ops.route_travel_seconds(route, c) - EPSILON:
                    route[:] = candidate
                    improved = True
                    improved_any = True
    return improved_any


def _or_opt_pass(
    ops: _RouteOps, routes: list[list[int]], windows: list[int], deadline: float | None = None
) -> bool:
    improved_any = False
    for c_from in range(len(routes)):
        for seg_len in (1, 2, 3):
            route_from = routes[c_from]
            if seg_len > len(route_from):
                continue
            for start in range(len(route_from) - seg_len + 1):
                if _expired(deadline):
                    return improved_any
                segment = route_from[start : start + seg_len]
                remainder = route_from[:start] + route_from[start + seg_len :]

                best_target: tuple[float, int, int, list[int]] | None = None
                for c_to in range(len(routes)):
                    base = remainder if c_to == c_from else routes[c_to]
                    for pos in range(len(base) + 1):
                        candidate = base[:pos] + segment + base[pos:]
                        if ops.route_duration_seconds(candidate, c_to) > windows[c_to]:
                            continue
                        if c_to == c_from:
                            delta = ops.route_travel_seconds(candidate, c_to) - ops.route_travel_seconds(
                                route_from, c_from
                            )
                        else:
                            delta = (
                                ops.route_travel_seconds(candidate, c_to)
                                - ops.route_travel_seconds(routes[c_to], c_to)
                            ) + (
                                ops.route_travel_seconds(remainder, c_from)
                                - ops.route_travel_seconds(route_from, c_from)
                            )
                        if best_target is None or delta < best_target[0]:
                            best_target = (delta, c_to, pos, candidate)

                if best_target is not None and best_target[0] < -EPSILON:
                    _, c_to, _pos, candidate = best_target
                    if c_to == c_from:
                        routes[c_from] = candidate
                    else:
                        routes[c_from] = remainder
                        routes[c_to] = candidate
                    improved_any = True
                    return improved_any  # restart pass with fresh route lists
    return improved_any


def _exchange_pass(
    ops: _RouteOps, routes: list[list[int]], windows: list[int], deadline: float | None = None
) -> bool:
    improved_any = False
    for c1 in range(len(routes)):
        for c2 in range(c1 + 1, len(routes)):
            r1, r2 = routes[c1], routes[c2]
            for i in range(len(r1)):
                if _expired(deadline):
                    return improved_any
                for j in range(len(r2)):
                    new_r1 = r1[:i] + [r2[j]] + r1[i + 1 :]
                    new_r2 = r2[:j] + [r1[i]] + r2[j + 1 :]
                    if ops.route_duration_seconds(new_r1, c1) > windows[c1]:
                        continue
                    if ops.route_duration_seconds(new_r2, c2) > windows[c2]:
                        continue
                    delta = (
                        ops.route_travel_seconds(new_r1, c1) + ops.route_travel_seconds(new_r2, c2)
                    ) - (ops.route_travel_seconds(r1, c1) + ops.route_travel_seconds(r2, c2))
                    if delta < -EPSILON:
                        routes[c1] = new_r1
                        routes[c2] = new_r2
                        return True  # restart pass with fresh route lists
    return improved_any


def _improve_to_convergence(
    ops: _RouteOps, routes: list[list[int]], windows: list[int], deadline: float | None = None
) -> None:
    """Runs to a local optimum, or until `deadline` (time.monotonic() value)
    expires — whichever comes first. On expiry the current routes are kept:
    every intermediate state is a complete, window-feasible solution, so the
    budget trades quality, never validity.
    """
    improved = True
    while improved and not _expired(deadline):
        improved = False
        for c, route in enumerate(routes):
            if _two_opt_pass(ops, route, c, deadline):
                improved = True
        if _or_opt_pass(ops, routes, windows, deadline):
            improved = True
        if _exchange_pass(ops, routes, windows, deadline):
            improved = True


@register_algorithm("cheapest_insertion_2opt")
class CheapestInsertion2OptAlgorithm(RoutingAlgorithmBase):
    display_name = "Cheapest Insertion + 2-opt/Or-opt"
    tier = AlgorithmTier.HEURISTIC

    def solve(
        self,
        instance: ProblemInstance,
        *,
        time_budget_seconds: float | None = None,
        seed: int | None = None,
    ) -> SolutionResult:
        ops = _RouteOps(instance)
        couriers = instance.couriers
        k = len(couriers)
        windows = [c.window_seconds for c in couriers]

        if ops.n == 0 or k == 0:
            unassigned = tuple(s.id for s in instance.stops) if k == 0 and ops.n > 0 else ()
            routes = tuple(
                ops.to_courier_route(couriers[c].id, [], c) for c in range(k)
            ) if k > 0 else ()
            return SolutionResult(
                routes=routes,
                unassigned_stop_ids=unassigned,
                total_duration_seconds=0.0,
                algorithm_key=self.key,
                algorithm_tier=self.tier,
                feasible=not unassigned,
            )

        # Construction is never budgeted — a complete construction is required
        # for a meaningful (feasibility-accurate) result. The budget only
        # limits how long we polish it.
        routes, unplaced = _construct_cheapest_insertion(ops, k, windows)
        deadline = time.monotonic() + time_budget_seconds if time_budget_seconds is not None else None
        _improve_to_convergence(ops, routes, windows, deadline)

        courier_routes = tuple(
            ops.to_courier_route(couriers[c].id, routes[c], c) for c in range(k)
        )
        total_duration = sum(r.total_duration_seconds for r in courier_routes)

        return SolutionResult(
            routes=courier_routes,
            unassigned_stop_ids=tuple(ops.stops[i].id for i in unplaced),
            total_duration_seconds=total_duration,
            algorithm_key=self.key,
            algorithm_tier=self.tier,
            feasible=not unplaced,
        )
