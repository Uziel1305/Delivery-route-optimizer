from app.optimization import solver
from app.optimization.benchmarking.synthetic import generate_synthetic_instance


def test_solve_with_courier_count_reduces_couriers_used():
    instance = generate_synthetic_instance(8, 4, seed=3, courier_window_seconds=10 * 3600)
    result = solver.solve_with_courier_count(instance, 2)
    assert result is not None
    assert result.feasible
    used = [r for r in result.routes if r.ordered_stop_ids]
    assert len(used) <= 2


def test_solve_with_courier_count_infeasible_returns_none():
    instance = generate_synthetic_instance(8, 4, seed=3, courier_window_seconds=1)
    result = solver.solve_with_courier_count(instance, 2)
    assert result is None


def test_solve_with_courier_count_rejects_out_of_range_n():
    instance = generate_synthetic_instance(5, 3, seed=1)
    assert solver.solve_with_courier_count(instance, 0) is None
    assert solver.solve_with_courier_count(instance, 4) is None


def test_reorder_single_route_matches_exact_optimum():
    instance = generate_synthetic_instance(6, 1, seed=9, courier_window_seconds=8 * 3600)
    courier = instance.couriers[0]
    reordered = solver.reorder_single_route(courier, instance.stops, instance.depot, instance.time_matrix)
    assert reordered is not None
    assert set(reordered.ordered_stop_ids) == {s.id for s in instance.stops}


def test_reorder_single_route_infeasible_returns_none():
    instance = generate_synthetic_instance(6, 1, seed=9, courier_window_seconds=1)
    courier = instance.couriers[0]
    reordered = solver.reorder_single_route(courier, instance.stops, instance.depot, instance.time_matrix)
    assert reordered is None
