from __future__ import annotations

from dataclasses import dataclass, field

from app.optimization.models import AlgorithmTier


@dataclass(frozen=True)
class AlgorithmConfig:
    # Provisional threshold — replace with a real value from
    # benchmarking/bench_runner.py once measured.
    optimal_tier_max_stops: int = 14
    optimal_tier_max_state_space: int = 5_000_000

    default_algorithm_key: dict[AlgorithmTier, str] = field(
        default_factory=lambda: {
            AlgorithmTier.OPTIMAL: "held_karp_exact",
            AlgorithmTier.HEURISTIC: "cheapest_insertion_2opt",
        }
    )

    default_time_budget_seconds: float = 240.0


DEFAULT_CONFIG = AlgorithmConfig()
