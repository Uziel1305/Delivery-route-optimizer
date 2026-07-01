"""Explicit imports so @register_algorithm decorators run at package import time.

brute_force.py is intentionally NOT imported here — it's a test-only
reference implementation and must never be reachable via the registry.
"""
from app.optimization.algorithms import construct_and_improve  # noqa: F401
from app.optimization.algorithms import exact_dp  # noqa: F401
