"""Exhaustive reference solver used only to cross-check HeldKarpExactAlgorithm
on tiny instances (n <= ~7) in tests/optimization/.

Deliberately NOT decorated with @register_algorithm and NOT imported by
algorithms/__init__.py — it must never be reachable via the production
registry. Complexity is O(k^n * n!), acceptable only for test fixtures.
"""
from __future__ import annotations

import itertools

from app.optimization.base import RoutingAlgorithmBase
from app.optimization.models import AlgorithmTier, ProblemInstance, SolutionResult


class BruteForceExactAlgorithm(RoutingAlgorithmBase):
    key = "brute_force_exact"
    display_name = "Brute Force (test-only)"
    tier = AlgorithmTier.EXPERIMENTAL

    def solve(
        self,
        instance: ProblemInstance,
        *,
        time_budget_seconds: float | None = None,
        seed: int | None = None,
    ) -> SolutionResult:
        stops = instance.stops
        couriers = instance.couriers
        n = len(stops)
        k = len(couriers)
        tm = instance.time_matrix
        matrix_idx = [tm.stop_index(s.id) for s in stops]
        start_idx = [tm.start_index(c.id) for c in couriers]
        end_idx = [tm.end_index(c.id) for c in couriers]
        dist = tm.matrix
        service_times = [s.service_time_seconds for s in stops]
        service_by_id = {s.id: s.service_time_seconds for s in stops}
        windows = [c.window_seconds for c in couriers]

        if n == 0:
            routes = tuple(
                self._route_from_order(c, (), service_by_id, tm)
                for c in couriers
            )
            return SolutionResult(
                routes=routes,
                unassigned_stop_ids=(),
                total_duration_seconds=0.0,
                algorithm_key=self.key,
                algorithm_tier=self.tier,
                feasible=True,
            )

        if k == 0:
            return SolutionResult(
                routes=(),
                unassigned_stop_ids=tuple(s.id for s in stops),
                total_duration_seconds=0.0,
                algorithm_key=self.key,
                algorithm_tier=self.tier,
                feasible=False,
            )

        def route_travel(order: tuple[int, ...], c: int) -> float:
            if not order:
                return 0.0
            total = dist[start_idx[c]][matrix_idx[order[0]]]
            for a, b in zip(order, order[1:]):
                total += dist[matrix_idx[a]][matrix_idx[b]]
            total += dist[matrix_idx[order[-1]]][end_idx[c]]
            return total

        def best_order_for_subset(subset: tuple[int, ...], c: int) -> tuple[float, tuple[int, ...]]:
            if not subset:
                return 0.0, ()
            best_travel = None
            best_order: tuple[int, ...] = ()
            for perm in itertools.permutations(subset):
                t = route_travel(perm, c)
                if best_travel is None or t < best_travel:
                    best_travel = t
                    best_order = perm
            return best_travel, best_order

        best_total: float | None = None
        best_orders: list[tuple[int, ...]] | None = None

        for assignment in itertools.product(range(k), repeat=n):
            groups: list[list[int]] = [[] for _ in range(k)]
            for stop_i, courier_i in enumerate(assignment):
                groups[courier_i].append(stop_i)

            total = 0.0
            orders: list[tuple[int, ...]] = []
            feasible = True
            for c in range(k):
                subset = tuple(groups[c])
                travel, order = best_order_for_subset(subset, c)
                service = sum(service_times[i] for i in subset)
                if subset and travel + service > windows[c]:
                    feasible = False
                    break
                total += travel + service
                orders.append(order)

            if not feasible:
                continue
            if best_total is None or total < best_total:
                best_total = total
                best_orders = orders

        if best_total is None or best_orders is None:
            return SolutionResult(
                routes=(),
                unassigned_stop_ids=tuple(s.id for s in stops),
                total_duration_seconds=0.0,
                algorithm_key=self.key,
                algorithm_tier=self.tier,
                feasible=False,
            )

        routes = tuple(
            self._route_from_order(
                couriers[c],
                tuple(stops[i].id for i in order),
                service_by_id,
                tm,
            )
            for c, order in enumerate(best_orders)
        )

        return SolutionResult(
            routes=routes,
            unassigned_stop_ids=(),
            total_duration_seconds=best_total,
            algorithm_key=self.key,
            algorithm_tier=self.tier,
            feasible=True,
        )
