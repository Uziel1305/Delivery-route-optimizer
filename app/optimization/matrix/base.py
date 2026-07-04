from __future__ import annotations

from abc import ABC, abstractmethod

from app.optimization.models import Courier, Stop, TimeMatrix


class TimeMatrixProvider(ABC):
    @abstractmethod
    def get_matrix(self, couriers: tuple[Courier, ...], stops: tuple[Stop, ...]) -> TimeMatrix:
        ...
