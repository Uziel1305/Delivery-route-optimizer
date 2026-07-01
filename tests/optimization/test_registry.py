import pytest

from app.optimization import registry
from app.optimization.exceptions import DuplicateAlgorithmKeyError, UnknownAlgorithmError
from app.optimization.models import AlgorithmTier

# Import the real package so the production algorithms are registered.
import app.optimization.algorithms  # noqa: F401


def test_known_algorithms_are_registered():
    assert registry.get_algorithm("held_karp_exact") is not None
    assert registry.get_algorithm("cheapest_insertion_2opt") is not None


def test_unknown_key_raises():
    with pytest.raises(UnknownAlgorithmError):
        registry.get_algorithm("does_not_exist")


def test_duplicate_key_raises():
    @registry.register_algorithm("test_dummy_algorithm")
    class _Dummy:
        pass

    with pytest.raises(DuplicateAlgorithmKeyError):

        @registry.register_algorithm("test_dummy_algorithm")
        class _Dummy2:
            pass


def test_default_algorithm_for_tier():
    optimal = registry.default_algorithm_for_tier(AlgorithmTier.OPTIMAL)
    heuristic = registry.default_algorithm_for_tier(AlgorithmTier.HEURISTIC)
    assert optimal.tier == AlgorithmTier.OPTIMAL
    assert heuristic.tier == AlgorithmTier.HEURISTIC


def test_brute_force_is_never_registered():
    # brute_force.py is test-only and must never be reachable via the
    # production registry (see algorithms/__init__.py).
    with pytest.raises(UnknownAlgorithmError):
        registry.get_algorithm("brute_force_exact")
