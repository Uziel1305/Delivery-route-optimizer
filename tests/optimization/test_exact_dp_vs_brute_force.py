"""Property-based cross-check: HeldKarpExactAlgorithm must agree with the
exhaustive BruteForceExactAlgorithm on small instances. This proves the
Phase 1/2 DP refinement in exact_dp.py is actually correct, not just
asymptotically right on paper.
"""
import math

from hypothesis import given, settings
from hypothesis import strategies as st

from app.optimization.algorithms.brute_force import BruteForceExactAlgorithm
from app.optimization.algorithms.exact_dp import HeldKarpExactAlgorithm
from app.optimization.benchmarking.synthetic import generate_synthetic_instance

exact = HeldKarpExactAlgorithm()
brute = BruteForceExactAlgorithm()


@settings(max_examples=25, deadline=None)
@given(
    n_stops=st.integers(min_value=0, max_value=6),
    n_couriers=st.integers(min_value=1, max_value=3),
    seed=st.integers(min_value=0, max_value=10_000),
)
def test_held_karp_matches_brute_force(n_stops, n_couriers, seed):
    instance = generate_synthetic_instance(
        n_stops, n_couriers, seed=seed, courier_window_seconds=6 * 3600
    )

    exact_result = exact.solve(instance)
    brute_result = brute.solve(instance)

    assert exact_result.feasible == brute_result.feasible
    if exact_result.feasible:
        assert math.isclose(
            exact_result.total_duration_seconds,
            brute_result.total_duration_seconds,
            rel_tol=1e-6,
            abs_tol=1e-6,
        )


@settings(max_examples=15, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_held_karp_matches_brute_force_tight_windows(seed):
    # Tight windows exercise the infeasible / partial-coverage code paths.
    instance = generate_synthetic_instance(
        5, 2, seed=seed, courier_window_seconds=600
    )
    exact_result = exact.solve(instance)
    brute_result = brute.solve(instance)
    assert exact_result.feasible == brute_result.feasible
