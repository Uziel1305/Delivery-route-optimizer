from __future__ import annotations

from abc import ABC, abstractmethod

from app.optimization.models import Depot, Stop, TimeMatrix


class TimeMatrixProvider(ABC):
    @abstractmethod
    def get_matrix(self, depot: Depot, stops: tuple[Stop, ...]) -> TimeMatrix:
        ...
