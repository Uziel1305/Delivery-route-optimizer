from __future__ import annotations

from app.optimization.matrix.base import TimeMatrixProvider
from app.optimization.models import Courier, Stop, TimeMatrix


class StaticTimeMatrixProvider(TimeMatrixProvider):
    """Wraps a pre-built, fixed TimeMatrix. Used in unit tests where the
    travel times must be exact known values, independent of coordinates.
    """

    def __init__(self, matrix: TimeMatrix):
        self._matrix = matrix

    def get_matrix(self, couriers: tuple[Courier, ...], stops: tuple[Stop, ...]) -> TimeMatrix:
        return self._matrix
