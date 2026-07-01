from app.optimization.models import Coordinate, Courier, CourierRoute, RouteLeg


def test_courier_window_seconds():
    courier = Courier(id="c1", start_time_seconds=8 * 3600, end_time_seconds=16 * 3600)
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
