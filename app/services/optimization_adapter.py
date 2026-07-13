"""ORM <-> app/optimization dataclass mapping boundary. This is the only
module that imports from both app.jobs (SQLAlchemy) and app.optimization
(framework-agnostic dataclasses) — nothing else should straddle that line.
"""
import hashlib

from sqlalchemy.orm import Session

from app.jobs.models import (
    CourierCountMode,
    Job,
    JobCourier,
    JobStop,
    Option,
    OptionCourierRoute,
    OptionRouteStop,
    OptionStatus,
    OptionUnassignedStop,
)
from app.optimization.models import Coordinate, Courier, ProblemInstance, SolutionResult, Stop, TimeMatrix


class MissingCourierLocations(Exception):
    """A JobCourier row has no start/end terminals (legacy depot-era day) —
    generation is impossible until the day is recreated or the locations
    are set for that day.
    """

    def __init__(self, courier_ids: list[str]):
        self.courier_ids = courier_ids
        super().__init__(f"couriers missing day locations: {courier_ids}")


def build_opt_couriers(job_couriers: list[JobCourier]) -> tuple[Courier, ...]:
    """Map JobCourier rows (with their per-day copied terminals) into
    optimization Couriers. Courier.id is the JobCourier row's own PK (not
    the underlying user id) — OptionCourierRoute.job_courier_id relies on that.
    """
    missing = [jc.id for jc in job_couriers if jc.start_lat is None or jc.end_lat is None]
    if missing:
        raise MissingCourierLocations(missing)
    return tuple(
        Courier(
            id=jc.id,
            start_time_seconds=jc.start_time_seconds,
            end_time_seconds=jc.end_time_seconds,
            start=Coordinate(lat=jc.start_lat, lon=jc.start_lon),
            end=Coordinate(lat=jc.end_lat, lon=jc.end_lon),
        )
        for jc in job_couriers
    )


def build_opt_stops(active_stops: list[JobStop]) -> tuple[Stop, ...]:
    return tuple(
        Stop(id=s.id, coordinate=Coordinate(lat=s.lat, lon=s.lon), service_time_seconds=s.service_time_seconds)
        for s in active_stops
    )


def build_problem_instance(
    job_couriers: list[JobCourier],
    active_stops: list[JobStop],
    time_matrix: TimeMatrix,
) -> ProblemInstance:
    return ProblemInstance(
        stops=build_opt_stops(active_stops),
        couriers=build_opt_couriers(job_couriers),
        time_matrix=time_matrix,
    )


def snapshot_hash(active_stops: list[JobStop], job_couriers: list[JobCourier]) -> str:
    """Fingerprint of everything an option's routes depend on: the stop set
    plus each courier's per-day terminals — so a day-level location edit
    also invalidates options generated before it.
    """
    stop_ids = sorted(s.id for s in active_stops)
    courier_parts = sorted(
        f"{jc.id}:{jc.start_lat}:{jc.start_lon}:{jc.end_lat}:{jc.end_lon}" for jc in job_couriers
    )
    blob = "|".join(stop_ids) + "#" + "|".join(courier_parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def create_pending_option(
    db: Session,
    job: Job,
    requested_courier_count: int | None,
    courier_count_mode: CourierCountMode | None,
    active_stops: list[JobStop],
    job_couriers: list[JobCourier],
    parent_option_id: str | None = None,
) -> Option:
    """Create the PENDING placeholder row the worker will later fill.

    The snapshot hash is taken NOW (at dispatch), so the worker can detect a
    day edited mid-solve by re-hashing at completion. algorithm_key/tier are
    placeholders until the solve picks them.
    """
    option = Option(
        job_id=job.id,
        label="Option",
        requested_courier_count=requested_courier_count,
        courier_count_mode=courier_count_mode,
        algorithm_key="",
        algorithm_tier="",
        total_duration_seconds=0.0,
        feasible=True,
        status=OptionStatus.PENDING,
        parent_option_id=parent_option_id,
        stops_snapshot_hash=snapshot_hash(active_stops, job_couriers),
    )
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


def fill_option(
    db: Session,
    option: Option,
    result: SolutionResult,
    *,
    final_status: OptionStatus = OptionStatus.ACTIVE,
) -> Option:
    """Write a solve result into an existing (PENDING) option row and flip
    its status. Commits."""
    option.algorithm_key = result.algorithm_key
    option.algorithm_tier = result.algorithm_tier.value
    option.total_duration_seconds = result.total_duration_seconds
    option.feasible = result.feasible
    option.status = final_status

    for route in result.routes:
        courier_route = OptionCourierRoute(
            option_id=option.id,
            job_courier_id=route.courier_id,
            total_travel_seconds=route.total_travel_seconds,
            total_service_seconds=route.total_service_seconds,
            total_duration_seconds=route.total_duration_seconds,
        )
        db.add(courier_route)
        db.flush()

        leg_by_to_stop = {leg.to_stop_id: leg.travel_seconds for leg in route.legs if leg.to_stop_id is not None}
        for idx, stop_id in enumerate(route.ordered_stop_ids):
            db.add(
                OptionRouteStop(
                    option_courier_route_id=courier_route.id,
                    job_stop_id=stop_id,
                    sequence_index=idx,
                    leg_travel_seconds=leg_by_to_stop.get(stop_id, 0.0),
                )
            )

    for stop_id in result.unassigned_stop_ids:
        db.add(OptionUnassignedStop(option_id=option.id, job_stop_id=stop_id))

    db.commit()
    db.refresh(option)
    return option
