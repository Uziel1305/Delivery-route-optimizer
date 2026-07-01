from __future__ import annotations

from app.optimization.base import RoutingAlgorithm
from app.optimization.exceptions import DuplicateAlgorithmKeyError, UnknownAlgorithmError
from app.optimization.models import AlgorithmTier

_REGISTRY: dict[str, RoutingAlgorithm] = {}


def register_algorithm(key: str):
    def decorator(cls: type[RoutingAlgorithm]) -> type[RoutingAlgorithm]:
        if key in _REGISTRY:
            raise DuplicateAlgorithmKeyError(f"Algorithm key already registered: {key!r}")
        # Set on the class (not just the registry's instance) so directly
        # instantiating the class outside the registry still has .key.
        cls.key = key
        instance = cls()
        _REGISTRY[key] = instance
        return cls

    return decorator


def get_algorithm(key: str) -> RoutingAlgorithm:
    try:
        return _REGISTRY[key]
    except KeyError as exc:
        raise UnknownAlgorithmError(f"No algorithm registered under key: {key!r}") from exc


def list_algorithms() -> list[RoutingAlgorithm]:
    return list(_REGISTRY.values())


def default_algorithm_for_tier(tier: AlgorithmTier) -> RoutingAlgorithm:
    from app.optimization.config import DEFAULT_CONFIG

    key = DEFAULT_CONFIG.default_algorithm_key[tier]
    return get_algorithm(key)
