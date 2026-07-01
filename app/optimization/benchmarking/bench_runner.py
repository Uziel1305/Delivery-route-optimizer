"""Times HeldKarpExactAlgorithm across (n_stops, n_couriers) combinations to
replace the provisional AlgorithmConfig.optimal_tier_max_stops placeholder
with a real, measured threshold.

Run directly: python -m app.optimization.benchmarking.bench_runner
"""
from __future__ import annotations

import time

from app.optimization.algorithms.exact_dp import HeldKarpExactAlgorithm
from app.optimization.benchmarking.synthetic import generate_synthetic_instance

STOP_COUNTS = [4, 6, 8, 10, 12, 14, 16, 18]
COURIER_COUNTS = [1, 2, 4, 8]
TIME_LIMIT_SECONDS = 30.0


def run() -> None:
    algorithm = HeldKarpExactAlgorithm()
    print(f"{'n_stops':>8} {'n_couriers':>10} {'seconds':>10} {'feasible':>9}")

    for n_stops in STOP_COUNTS:
        for n_couriers in COURIER_COUNTS:
            instance = generate_synthetic_instance(n_stops, n_couriers, seed=42)
            start = time.perf_counter()
            result = algorithm.solve(instance)
            elapsed = time.perf_counter() - start

            print(f"{n_stops:>8} {n_couriers:>10} {elapsed:>10.3f} {str(result.feasible):>9}")

            if elapsed > TIME_LIMIT_SECONDS:
                print(f"  -> exceeded {TIME_LIMIT_SECONDS}s budget, skipping larger n_stops for this courier count")
                break


if __name__ == "__main__":
    run()
