"""Hand-built-matrix tests pinning down the multi-terminal semantics:
routes run courier start -> stops -> courier end, and an idle courier
(no stops) drives nothing and costs zero.
"""
import math

from app.optimization.algorithms.exact_dp import HeldKarpExactAlgorithm
from app.optimization.models import (
    Coordinate,
    Courier,
    ProblemInstance,
    Stop,
    TimeMatrix,
    end_point_id,
    start_point_id,
)

exact = HeldKarpExactAlgorithm()

ANY = Coordinate(lat=32.0, lon=34.8)  # coordinates are irrelevant with a static matrix
BIG = 1000.0


def _matrix(point_ids: list[str], entries: dict[tuple[str, str], float]) -> TimeMatrix:
    rows = []
    for a in point_ids:
        row = []
        for b in point_ids:
            if a == b:
                row.append(0.0)
            else:
                row.append(entries.get((a, b), BIG))
        rows.append(tuple(row))
    return TimeMatrix(matrix=tuple(rows), point_ids=tuple(point_ids))


def test_route_runs_start_to_end_not_round_trip():
    courier = Courier(id="c1", start_time_seconds=0, end_time_seconds=3600, start=ANY, end=ANY)
    stops = (Stop(id="s1", coordinate=ANY), Stop(id="s2", coordinate=ANY))
    tm = _matrix(
        [start_point_id("c1"), end_point_id("c1"), "s1", "s2"],
        {
            (start_point_id("c1"), "s1"): 10.0,
            ("s1", "s2"): 5.0,
            ("s2", end_point_id("c1")): 10.0,
        },
    )
    instance = ProblemInstance(stops=stops, couriers=(courier,), time_matrix=tm)

    result = exact.solve(instance)

    assert result.feasible
    route = result.routes[0]
    assert route.ordered_stop_ids == ("s1", "s2")
    assert math.isclose(route.total_travel_seconds, 25.0)
    # First leg leaves the start terminal, last leg arrives at the end terminal.
    assert route.legs[0].from_stop_id is None
    assert route.legs[-1].to_stop_id is None


def test_idle_courier_costs_zero():
    near = Courier(id="near", start_time_seconds=0, end_time_seconds=3600, start=ANY, end=ANY)
    far = Courier(id="far", start_time_seconds=0, end_time_seconds=3600, start=ANY, end=ANY)
    stops = (Stop(id="s1", coordinate=ANY),)
    tm = _matrix(
        [
            start_point_id("near"),
            end_point_id("near"),
            start_point_id("far"),
            end_point_id("far"),
            "s1",
        ],
        {
            (start_point_id("near"), "s1"): 7.0,
            ("s1", end_point_id("near")): 8.0,
        },
    )
    instance = ProblemInstance(stops=stops, couriers=(near, far), time_matrix=tm)

    result = exact.solve(instance)

    assert result.feasible
    by_id = {r.courier_id: r for r in result.routes}
    assert by_id["near"].ordered_stop_ids == ("s1",)
    assert by_id["far"].ordered_stop_ids == ()
    assert by_id["far"].total_travel_seconds == 0.0
    assert by_id["far"].legs == ()
    assert math.isclose(result.total_duration_seconds, 15.0)
