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
from app.optimization.models import Coordinate, Courier, Depot, ProblemInstance, SolutionResult, Stop, TimeMatrix


def build_problem_instance(
    job: Job,
    job_couriers: list[JobCourier],
    active_stops: list[JobStop],
    time_matrix: TimeMatrix,
) -> ProblemInstance:
    depot = Depot(coordinate=Coordinate(lat=job.depot_lat, lon=job.depot_lon))
    stops = tuple(
        Stop(id=s.id, coordinate=Coordinate(lat=s.lat, lon=s.lon), service_time_seconds=s.service_time_seconds)
        for s in active_stops
    )
    # Courier.id is the JobCourier row's own PK (not the underlying user id) —
    # OptionCourierRoute.job_courier_id below relies on that.
    couriers = tuple(
        Courier(id=jc.id, start_time_seconds=jc.start_time_seconds, end_time_seconds=jc.end_time_seconds)
        for jc in job_couriers
    )
    return ProblemInstance(depot=depot, stops=stops, couriers=couriers, time_matrix=time_matrix)


def stops_snapshot_hash(active_stops: list[JobStop]) -> str:
    ids = sorted(s.id for s in active_stops)
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()


def persist_solution(
    db: Session,
    job: Job,
    requested_courier_count: int | None,
    courier_count_mode: CourierCountMode | None,
    result: SolutionResult,
    active_stops: list[JobStop],
    parent_option_id: str | None = None,
) -> Option:
    option = Option(
        job_id=job.id,
        label="Option",
        requested_courier_count=requested_courier_count,
        courier_count_mode=courier_count_mode,
        algorithm_key=result.algorithm_key,
        algorithm_tier=result.algorithm_tier.value,
        total_duration_seconds=result.total_duration_seconds,
        feasible=result.feasible,
        status=OptionStatus.ACTIVE,
        parent_option_id=parent_option_id,
        stops_snapshot_hash=stops_snapshot_hash(active_stops),
    )
    db.add(option)
    db.flush()

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
