from app.optimization.models import (
    Coordinate,
    Courier,
    CourierRoute,
    RouteLeg,
    TimeMatrix,
    end_point_id,
    start_point_id,
)

TLV = Coordinate(lat=32.08, lon=34.78)
JLM = Coordinate(lat=31.78, lon=35.22)


def test_courier_window_seconds():
    courier = Courier(
        id="c1", start_time_seconds=8 * 3600, end_time_seconds=16 * 3600, start=TLV, end=JLM
    )
    assert courier.window_seconds == 8 * 3600


def test_courier_route_total_duration():
    route = CourierRoute(
        courier_id="c1",
        ordered_stop_ids=("s1",),
        legs=(
            RouteLeg(from_stop_id=None, to_stop_id="s1", travel_seconds=100.0),
            RouteLeg(from_stop_id="s1", to_stop_id=None, travel_seconds=100.0),
        ),
        total_travel_seconds=200.0,
        total_service_seconds=60.0,
    )
    assert route.total_duration_seconds == 260.0


def test_coordinate_is_frozen():
    coord = Coordinate(lat=32.0, lon=34.0)
    try:
        coord.lat = 10.0
        assert False, "Coordinate should be immutable"
    except AttributeError:
        pass


def test_time_matrix_point_lookups():
    matrix = TimeMatrix(
        matrix=((0.0, 1.0, 2.0), (1.0, 0.0, 3.0), (2.0, 3.0, 0.0)),
        point_ids=(start_point_id("c1"), end_point_id("c1"), "s1"),
    )
    assert matrix.start_index("c1") == 0
    assert matrix.end_index("c1") == 1
    assert matrix.stop_index("s1") == 2
    assert matrix.travel_seconds(0, 2) == 2.0
    assert matrix.size == 3
