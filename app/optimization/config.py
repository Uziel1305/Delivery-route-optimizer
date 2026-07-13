from __future__ import annotations

from dataclasses import dataclass, field

from app.optimization.models import AlgorithmTier


@dataclass(frozen=True)
class AlgorithmConfig:
    # Benchmarked 2026-07-13 (bench_runner.py / benchmarks/): exact solves
    # take 1.5s (1 courier) to 8.5s (5 couriers) at 14 stops and 13-77s at
    # 16 — so 14 is the largest defensible exact tier.
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
