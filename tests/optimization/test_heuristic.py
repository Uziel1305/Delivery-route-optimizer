import time

from app.optimization.algorithms.construct_and_improve import CheapestInsertion2OptAlgorithm
from app.optimization.algorithms.exact_dp import HeldKarpExactAlgorithm
from app.optimization.benchmarking.synthetic import generate_synthetic_instance

heuristic = CheapestInsertion2OptAlgorithm()
exact = HeldKarpExactAlgorithm()


def test_heuristic_within_tolerance_of_optimal():
    for seed in range(5):
        instance = generate_synthetic_instance(8, 2, seed=seed, courier_window_seconds=8 * 3600)
        exact_result = exact.solve(instance)
        heuristic_result = heuristic.solve(instance)

        assert exact_result.feasible
        assert heuristic_result.feasible
        assert heuristic_result.total_duration_seconds >= exact_result.total_duration_seconds - 1e-6
        assert heuristic_result.total_duration_seconds <= exact_result.total_duration_seconds * 1.5


def test_heuristic_is_deterministic():
    instance = generate_synthetic_instance(20, 3, seed=7, courier_window_seconds=8 * 3600)
    result_a = heuristic.solve(instance)
    result_b = heuristic.solve(instance)
    assert result_a.total_duration_seconds == result_b.total_duration_seconds
    assert [r.ordered_stop_ids for r in result_a.routes] == [r.ordered_stop_ids for r in result_b.routes]


def test_heuristic_reports_unassigned_when_infeasible():
    instance = generate_synthetic_instance(10, 1, seed=1, courier_window_seconds=1)
    result = heuristic.solve(instance)
    assert not result.feasible
    assert len(result.unassigned_stop_ids) > 0


def test_heuristic_handles_zero_stops():
    instance = generate_synthetic_instance(0, 2, seed=1)
    result = heuristic.solve(instance)
    assert result.feasible
    assert result.total_duration_seconds == 0.0


def test_time_budget_caps_improvement_and_stays_valid():
    """Anytime behavior: a tight budget must cut the improvement phase short
    (construction is deliberately unbudgeted) while still returning a
    complete, feasible solution covering every stop.
    """
    instance = generate_synthetic_instance(80, 4, seed=3, courier_window_seconds=8 * 3600)

    t0 = time.perf_counter()
    unbudgeted = heuristic.solve(instance)
    unbudgeted_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    budgeted = heuristic.solve(instance, time_budget_seconds=0.2)
    budgeted_seconds = time.perf_counter() - t0

    assert budgeted_seconds < unbudgeted_seconds
    assert budgeted.feasible
    assigned = [sid for route in budgeted.routes for sid in route.ordered_stop_ids]
    assert len(assigned) == len(instance.stops)
    # The budgeted answer may be worse, but never better than what full
    # convergence found (both start from the same deterministic construction).
    assert budgeted.total_duration_seconds >= unbudgeted.total_duration_seconds - 1e-6
