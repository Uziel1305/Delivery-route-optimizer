from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.auth.models import CourierProfile, User, UserRole
from app.config import get_settings
from app.database import get_db
from app.jobs.models import (
    CourierCountMode,
    Job,
    JobCourier,
    JobStatus,
    JobStop,
    Option,
    OptionCourierRoute,
    OptionRouteStop,
    OptionStatus,
    OptionUnassignedStop,
    SavedLocation,
)
from app.jobs.schemas import (
    AddStopsFromLocationsRequest,
    AssignmentStopOut,
    CourierJobOut,
    CourierRouteOut,
    GenerateWithNRequest,
    JobCourierLocationsUpdateRequest,
    JobCourierOut,
    JobCreateRequest,
    JobDetailOut,
    JobOut,
    JobSummaryOut,
    OptionOut,
    RouteStopOut,
    SavedLocationCreateRequest,
    SavedLocationOut,
    StopCreateRequest,
    StopOut,
    SwapRequest,
)
from app.optimization import solver as opt_solver
from app.optimization.matrix.osrm_provider import OsrmTimeMatrixProvider
from app.optimization.models import Coordinate, Courier as OptCourier, Stop as OptStop
from app.services.optimization_adapter import (
    MissingCourierLocations,
    build_opt_couriers,
    create_pending_option,
)
from app.tasks.optimization_tasks import run_optimization_task

LOCATION_FIELDS = ("start_lat", "start_lon", "start_address_label", "end_lat", "end_lon", "end_address_label")

settings = get_settings()
router = APIRouter(tags=["jobs"])


def _get_owned_job(db: Session, job_id: str, manager: User) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.manager_id == manager.id).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return job


def _option_to_out(db: Session, option: Option) -> OptionOut:
    courier_routes = db.query(OptionCourierRoute).filter(OptionCourierRoute.option_id == option.id).all()
    routes_out = []
    for cr in courier_routes:
        stops = (
            db.query(OptionRouteStop)
            .filter(OptionRouteStop.option_courier_route_id == cr.id)
            .order_by(OptionRouteStop.sequence_index)
            .all()
        )
        routes_out.append(
            CourierRouteOut(
                job_courier_id=cr.job_courier_id,
                total_travel_seconds=cr.total_travel_seconds,
                total_service_seconds=cr.total_service_seconds,
                total_duration_seconds=cr.total_duration_seconds,
                stops=[
                    RouteStopOut(
                        job_stop_id=s.job_stop_id,
                        sequence_index=s.sequence_index,
                        leg_travel_seconds=s.leg_travel_seconds,
                    )
                    for s in stops
                ],
            )
        )
    unassigned = db.query(OptionUnassignedStop).filter(OptionUnassignedStop.option_id == option.id).all()

    return OptionOut(
        id=option.id,
        job_id=option.job_id,
        label=option.label,
        requested_courier_count=option.requested_courier_count,
        courier_count_mode=option.courier_count_mode,
        algorithm_key=option.algorithm_key,
        algorithm_tier=option.algorithm_tier,
        total_duration_seconds=option.total_duration_seconds,
        feasible=option.feasible,
        status=option.status,
        error_detail=option.error_detail,
        parent_option_id=option.parent_option_id,
        courier_routes=routes_out,
        unassigned_stop_ids=[u.job_stop_id for u in unassigned],
    )


def _dispatch_generation(
    db: Session,
    job: Job,
    requested_courier_count: int | None,
    parent_option_id: str | None = None,
) -> Option:
    """Create a PENDING option and hand it to the Celery worker. Cheap
    validation (couriers have terminals) happens here so the common mistakes
    still fail fast as 422s; solver-level infeasibility is discovered by the
    worker and lands on the option as FAILED + error_detail.
    """
    job_couriers = db.query(JobCourier).filter(JobCourier.job_id == job.id).all()
    try:
        build_opt_couriers(job_couriers)  # validation only
    except MissingCourierLocations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="couriers on this day have no start/end locations (created before per-courier locations) — recreate the delivery day",
        )

    active_stops = db.query(JobStop).filter(JobStop.job_id == job.id, JobStop.deleted_at.is_(None)).all()
    mode = CourierCountMode.EXACT if requested_courier_count is not None else None
    option = create_pending_option(
        db, job, requested_courier_count, mode, active_stops, job_couriers, parent_option_id=parent_option_id
    )
    run_optimization_task.delay(option.id)
    return option


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreateRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    # Copy-on-assign: each courier's current default terminals are copied
    # into the JobCourier row, so later profile changes never rewrite this
    # day. Couriers without locations can't be planned around — reject.
    courier_ids = [jc.courier_id for jc in payload.couriers]
    profiles = {
        p.user_id: p
        for p in db.query(CourierProfile).filter(CourierProfile.user_id.in_(courier_ids)).all()
    }
    missing = [cid for cid in courier_ids if cid not in profiles or not profiles[cid].has_locations]
    if missing:
        usernames = [u.username for u in db.query(User).filter(User.id.in_(missing)).all()]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "couriers have no start/end locations set", "couriers": usernames},
        )

    job = Job(
        manager_id=manager.id,
        delivery_date=payload.delivery_date,
    )
    db.add(job)
    db.flush()

    for jc in payload.couriers:
        profile = profiles[jc.courier_id]
        db.add(
            JobCourier(
                job_id=job.id,
                courier_id=jc.courier_id,
                start_time_seconds=jc.start_time_seconds,
                end_time_seconds=jc.end_time_seconds,
                **{f: getattr(profile, f) for f in LOCATION_FIELDS},
            )
        )

    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobSummaryOut])
def list_jobs(
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    jobs = db.query(Job).filter(Job.manager_id == manager.id).order_by(Job.created_at.desc()).all()
    summaries = []
    for job in jobs:
        stop_count = (
            db.query(JobStop).filter(JobStop.job_id == job.id, JobStop.deleted_at.is_(None)).count()
        )
        courier_count = db.query(JobCourier).filter(JobCourier.job_id == job.id).count()
        summaries.append(
            JobSummaryOut(
                id=job.id,
                status=job.status,
                published_option_id=job.published_option_id,
                delivery_date=job.delivery_date,
                stop_count=stop_count,
                courier_count=courier_count,
            )
        )
    return summaries


@router.get("/jobs/{job_id}", response_model=JobDetailOut)
def get_job(
    job_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(db, job_id, manager)
    return JobDetailOut(
        id=job.id,
        status=job.status,
        published_option_id=job.published_option_id,
        delivery_date=job.delivery_date,
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(db, job_id, manager)

    # No FK cascades in the schema, so tear down children manually, leaves first.
    option_ids = [oid for (oid,) in db.query(Option.id).filter(Option.job_id == job.id).all()]
    if option_ids:
        route_ids = [
            rid
            for (rid,) in db.query(OptionCourierRoute.id)
            .filter(OptionCourierRoute.option_id.in_(option_ids))
            .all()
        ]
        if route_ids:
            db.query(OptionRouteStop).filter(
                OptionRouteStop.option_courier_route_id.in_(route_ids)
            ).delete()
        db.query(OptionUnassignedStop).filter(OptionUnassignedStop.option_id.in_(option_ids)).delete()
        db.query(OptionCourierRoute).filter(OptionCourierRoute.option_id.in_(option_ids)).delete()

        # jobs.published_option_id and options.job_id point at each other, so
        # break the cycle before the options can go.
        job.published_option_id = None
        db.flush()
        db.query(Option).filter(Option.job_id == job.id).delete()

    db.query(JobStop).filter(JobStop.job_id == job.id).delete()
    db.query(JobCourier).filter(JobCourier.job_id == job.id).delete()
    db.delete(job)
    db.commit()


@router.get("/jobs/{job_id}/stops", response_model=list[StopOut])
def list_stops(
    job_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(db, job_id, manager)
    return (
        db.query(JobStop)
        .filter(JobStop.job_id == job.id, JobStop.deleted_at.is_(None))
        .order_by(JobStop.created_at)
        .all()
    )


@router.get("/jobs/{job_id}/couriers", response_model=list[JobCourierOut])
def list_job_couriers(
    job_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(db, job_id, manager)
    rows = (
        db.query(JobCourier, User)
        .join(User, User.id == JobCourier.courier_id)
        .filter(JobCourier.job_id == job.id)
        .all()
    )
    return [
        JobCourierOut(
            job_courier_id=jc.id,
            courier_id=jc.courier_id,
            username=user.username,
            start_time_seconds=jc.start_time_seconds,
            end_time_seconds=jc.end_time_seconds,
            **{f: getattr(jc, f) for f in LOCATION_FIELDS},
        )
        for jc, user in rows
    ]


@router.put("/jobs/{job_id}/couriers/{job_courier_id}/locations", response_model=JobCourierOut)
def update_job_courier_locations(
    job_id: str,
    job_courier_id: str,
    payload: JobCourierLocationsUpdateRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    """Day-only edit of one courier's start/end for this delivery day — the
    courier's profile defaults are untouched. Existing ACTIVE options no
    longer match the day's terminals, so they flip to STALE (same treatment
    as deleting a stop); the published option is deliberately left alone.
    """
    job = _get_owned_job(db, job_id, manager)
    if job.status == JobStatus.ARCHIVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="job is archived")
    jc = (
        db.query(JobCourier)
        .filter(JobCourier.id == job_courier_id, JobCourier.job_id == job.id)
        .first()
    )
    if jc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    for f in LOCATION_FIELDS:
        setattr(jc, f, getattr(payload, f))

    active_options = (
        db.query(Option)
        .filter(Option.job_id == job.id, Option.status == OptionStatus.ACTIVE)
        .all()
    )
    for opt in active_options:
        opt.status = OptionStatus.STALE
    db.commit()

    user = db.get(User, jc.courier_id)
    return JobCourierOut(
        job_courier_id=jc.id,
        courier_id=jc.courier_id,
        username=user.username if user else "",
        start_time_seconds=jc.start_time_seconds,
        end_time_seconds=jc.end_time_seconds,
        **{f: getattr(jc, f) for f in LOCATION_FIELDS},
    )


@router.post("/locations", response_model=SavedLocationOut, status_code=status.HTTP_201_CREATED)
def create_saved_location(
    payload: SavedLocationCreateRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    location = SavedLocation(
        manager_id=manager.id,
        lat=payload.lat,
        lon=payload.lon,
        service_time_seconds=payload.service_time_seconds,
        address_label=payload.address_label,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("/locations", response_model=list[SavedLocationOut])
def list_saved_locations(
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    return (
        db.query(SavedLocation)
        .filter(SavedLocation.manager_id == manager.id)
        .order_by(SavedLocation.created_at)
        .all()
    )


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_location(
    location_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    location = (
        db.query(SavedLocation)
        .filter(SavedLocation.id == location_id, SavedLocation.manager_id == manager.id)
        .first()
    )
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    db.delete(location)
    db.commit()


@router.post("/jobs/{job_id}/stops/from-locations", response_model=list[StopOut], status_code=status.HTTP_201_CREATED)
def add_stops_from_locations(
    job_id: str,
    payload: AddStopsFromLocationsRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(db, job_id, manager)

    locations = (
        db.query(SavedLocation)
        .filter(SavedLocation.id.in_(payload.location_ids), SavedLocation.manager_id == manager.id)
        .all()
    )
    if len(locations) != len(set(payload.location_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="one or more locations not found")

    new_stops = [
        JobStop(
            job_id=job.id,
            lat=loc.lat,
            lon=loc.lon,
            service_time_seconds=loc.service_time_seconds,
            address_label=loc.address_label,
        )
        for loc in locations
    ]
    db.add_all(new_stops)
    db.commit()
    for s in new_stops:
        db.refresh(s)
    return new_stops


@router.post("/jobs/{job_id}/stops", response_model=StopOut, status_code=status.HTTP_201_CREATED)
def add_stop(
    job_id: str,
    payload: StopCreateRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(db, job_id, manager)
    stop = JobStop(
        job_id=job.id,
        lat=payload.lat,
        lon=payload.lon,
        service_time_seconds=payload.service_time_seconds,
        address_label=payload.address_label,
    )
    db.add(stop)
    db.commit()
    db.refresh(stop)
    return stop


@router.delete("/jobs/{job_id}/stops/{stop_id}", response_model=OptionOut | None)
def delete_stop(
    job_id: str,
    stop_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    """Soft delete. All ACTIVE options flip to STALE (they no longer match
    the stop set); the most recent one is regenerated as a new Option with
    parent_option_id pointing at it. The published option is deliberately
    left untouched — a courier's live route only changes when the manager
    explicitly generates and publishes a new option.
    """
    job = _get_owned_job(db, job_id, manager)
    stop = db.query(JobStop).filter(JobStop.id == stop_id, JobStop.job_id == job.id).first()
    if stop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    stop.deleted_at = datetime.now(timezone.utc)

    active_options = (
        db.query(Option)
        .filter(Option.job_id == job.id, Option.status == OptionStatus.ACTIVE)
        .order_by(Option.created_at.desc())
        .all()
    )
    for opt in active_options:
        opt.status = OptionStatus.STALE
    db.commit()

    if not active_options:
        return None

    # Regenerate asynchronously: the response carries a PENDING option the
    # frontend polls; couriers without locations just skip regeneration
    # (matches the old silent-None behavior).
    parent_option_id = active_options[0].id
    try:
        option = _dispatch_generation(db, job, requested_courier_count=None, parent_option_id=parent_option_id)
    except HTTPException:
        return None
    return _option_to_out(db, option)


@router.post("/jobs/{job_id}/options/generate", response_model=OptionOut)
def generate_option(
    job_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    """Returns immediately with a PENDING option; a Celery worker solves it.
    Poll GET /jobs/{id}/options until the status flips to active (or failed,
    with the reason in error_detail).
    """
    job = _get_owned_job(db, job_id, manager)
    option = _dispatch_generation(db, job, requested_courier_count=None)
    return _option_to_out(db, option)


@router.post("/jobs/{job_id}/options/generate-with-n-couriers", response_model=OptionOut)
def generate_with_n_couriers(
    job_id: str,
    payload: GenerateWithNRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    """Async like plain generate. Out-of-range N fails fast as a 422 here;
    genuine infeasibility with a valid N is discovered by the worker and
    lands as a FAILED option (existing options stay untouched either way).
    """
    job = _get_owned_job(db, job_id, manager)
    assigned = db.query(JobCourier).filter(JobCourier.job_id == job.id).count()
    if payload.courier_count <= 0 or payload.courier_count > assigned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"courier_count must be between 1 and {assigned} (couriers assigned to this day)",
        )
    option = _dispatch_generation(db, job, requested_courier_count=payload.courier_count)
    return _option_to_out(db, option)


@router.get("/jobs/{job_id}/options", response_model=list[OptionOut])
def list_options(
    job_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(db, job_id, manager)
    options = db.query(Option).filter(Option.job_id == job.id).all()
    return [_option_to_out(db, o) for o in options]


@router.get("/jobs/{job_id}/options/{option_id}", response_model=OptionOut)
def get_option(
    job_id: str,
    option_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(db, job_id, manager)
    option = db.query(Option).filter(Option.id == option_id, Option.job_id == job.id).first()
    if option is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _option_to_out(db, option)


@router.delete("/jobs/{job_id}/options/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_failed_option(
    job_id: str,
    option_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    """Dismiss a FAILED option card. Only FAILED options are deletable —
    everything else is history (stale/superseded) or live (active/published/
    pending) and must not be removed this way.
    """
    job = _get_owned_job(db, job_id, manager)
    option = db.query(Option).filter(Option.id == option_id, Option.job_id == job.id).first()
    if option is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if option.status != OptionStatus.FAILED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only failed options can be dismissed")

    # FAILED options have no children, but delete defensively (no FK cascades).
    route_ids = [
        rid for (rid,) in db.query(OptionCourierRoute.id).filter(OptionCourierRoute.option_id == option.id).all()
    ]
    if route_ids:
        db.query(OptionRouteStop).filter(OptionRouteStop.option_courier_route_id.in_(route_ids)).delete(
            synchronize_session=False
        )
        db.query(OptionCourierRoute).filter(OptionCourierRoute.id.in_(route_ids)).delete(synchronize_session=False)
    db.query(OptionUnassignedStop).filter(OptionUnassignedStop.option_id == option.id).delete(
        synchronize_session=False
    )
    db.delete(option)
    db.commit()


@router.post("/jobs/{job_id}/options/{option_id}/swap", response_model=OptionOut)
def swap_stop(
    job_id: str,
    option_id: str,
    payload: SwapRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    """A swap only ever moves which courier a stop belongs to — never
    manually reorders within a route. Both affected routes are re-solved
    exactly (or heuristically, for larger stop counts) and, if either
    becomes infeasible, nothing is written. This mutates the option in
    place; unlike "try N couriers" it does not create a new Option row.
    """
    job = _get_owned_job(db, job_id, manager)
    option = db.query(Option).filter(Option.id == option_id, Option.job_id == job.id).first()
    if option is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if option.status != OptionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="option is not active")

    from_route = (
        db.query(OptionCourierRoute)
        .join(OptionRouteStop, OptionRouteStop.option_courier_route_id == OptionCourierRoute.id)
        .filter(OptionCourierRoute.option_id == option.id, OptionRouteStop.job_stop_id == payload.job_stop_id)
        .first()
    )
    to_route = (
        db.query(OptionCourierRoute)
        .filter(
            OptionCourierRoute.option_id == option.id,
            OptionCourierRoute.job_courier_id == payload.to_job_courier_id,
        )
        .first()
    )
    if from_route is None or to_route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stop or target courier not in this option")
    if from_route.id == to_route.id:
        return _option_to_out(db, option)

    from_job_courier = db.get(JobCourier, from_route.job_courier_id)
    to_job_courier = db.get(JobCourier, to_route.job_courier_id)
    if any(jc.start_lat is None or jc.end_lat is None for jc in (from_job_courier, to_job_courier)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="couriers on this day have no start/end locations",
        )

    from_stop_ids = [
        s.job_stop_id
        for s in db.query(OptionRouteStop)
        .filter(OptionRouteStop.option_courier_route_id == from_route.id)
        .order_by(OptionRouteStop.sequence_index)
        .all()
        if s.job_stop_id != payload.job_stop_id
    ]
    to_stop_ids = [
        s.job_stop_id
        for s in db.query(OptionRouteStop)
        .filter(OptionRouteStop.option_courier_route_id == to_route.id)
        .order_by(OptionRouteStop.sequence_index)
        .all()
    ] + [payload.job_stop_id]

    all_stop_ids = set(from_stop_ids) | set(to_stop_ids)
    job_stops_by_id = {
        s.id: s
        for s in db.query(JobStop).filter(JobStop.id.in_(all_stop_ids), JobStop.deleted_at.is_(None)).all()
    }

    def to_opt_courier(jc: JobCourier) -> OptCourier:
        return OptCourier(
            id=jc.id,
            start_time_seconds=jc.start_time_seconds,
            end_time_seconds=jc.end_time_seconds,
            start=Coordinate(lat=jc.start_lat, lon=jc.start_lon),
            end=Coordinate(lat=jc.end_lat, lon=jc.end_lon),
        )

    from_courier = to_opt_courier(from_job_courier)
    to_courier = to_opt_courier(to_job_courier)

    all_active_stops = db.query(JobStop).filter(JobStop.job_id == job.id, JobStop.deleted_at.is_(None)).all()
    matrix_provider = OsrmTimeMatrixProvider(base_url=settings.osrm_base_url)
    opt_stops = tuple(
        OptStop(id=s.id, coordinate=Coordinate(lat=s.lat, lon=s.lon), service_time_seconds=s.service_time_seconds)
        for s in all_active_stops
    )
    time_matrix = matrix_provider.get_matrix((from_courier, to_courier), opt_stops)

    def to_opt_stops(ids: list[str]) -> tuple:
        return tuple(
            OptStop(
                id=job_stops_by_id[i].id,
                coordinate=Coordinate(lat=job_stops_by_id[i].lat, lon=job_stops_by_id[i].lon),
                service_time_seconds=job_stops_by_id[i].service_time_seconds,
            )
            for i in ids
        )

    new_from_route = opt_solver.reorder_single_route(from_courier, to_opt_stops(from_stop_ids), time_matrix)
    new_to_route = opt_solver.reorder_single_route(to_courier, to_opt_stops(to_stop_ids), time_matrix)

    if new_from_route is None or new_to_route is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="swap does not fit within courier windows")

    for route, opt_route in ((from_route, new_from_route), (to_route, new_to_route)):
        db.query(OptionRouteStop).filter(OptionRouteStop.option_courier_route_id == route.id).delete()
        leg_by_to_stop = {leg.to_stop_id: leg.travel_seconds for leg in opt_route.legs if leg.to_stop_id is not None}
        for idx, sid in enumerate(opt_route.ordered_stop_ids):
            db.add(
                OptionRouteStop(
                    option_courier_route_id=route.id,
                    job_stop_id=sid,
                    sequence_index=idx,
                    leg_travel_seconds=leg_by_to_stop.get(sid, 0.0),
                )
            )
        route.total_travel_seconds = opt_route.total_travel_seconds
        route.total_service_seconds = opt_route.total_service_seconds
        route.total_duration_seconds = opt_route.total_duration_seconds

    all_routes = db.query(OptionCourierRoute).filter(OptionCourierRoute.option_id == option.id).all()
    option.total_duration_seconds = sum(r.total_duration_seconds for r in all_routes)
    db.commit()
    db.refresh(option)
    return _option_to_out(db, option)


@router.post("/jobs/{job_id}/options/{option_id}/publish", response_model=OptionOut)
def publish_option(
    job_id: str,
    option_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(db, job_id, manager)
    option = db.query(Option).filter(Option.id == option_id, Option.job_id == job.id).first()
    if option is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if option.status != OptionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="option is not active")

    if job.published_option_id is not None:
        previous = db.get(Option, job.published_option_id)
        if previous is not None:
            previous.status = OptionStatus.SUPERSEDED

    option.status = OptionStatus.PUBLISHED
    job.published_option_id = option.id
    job.status = JobStatus.PUBLISHED
    db.commit()
    db.refresh(option)
    return _option_to_out(db, option)


def _assignment_query(db: Session, courier_id: str, job_id: str | None = None):
    query = (
        db.query(OptionRouteStop, JobStop)
        .join(OptionCourierRoute, OptionRouteStop.option_courier_route_id == OptionCourierRoute.id)
        .join(Option, OptionCourierRoute.option_id == Option.id)
        .join(JobCourier, OptionCourierRoute.job_courier_id == JobCourier.id)
        .join(JobStop, OptionRouteStop.job_stop_id == JobStop.id)
        .filter(
            Option.status == OptionStatus.PUBLISHED,
            JobCourier.courier_id == courier_id,  # from the authenticated user, never a path/body param
            JobStop.deleted_at.is_(None),
        )
    )
    if job_id is not None:
        query = query.filter(JobCourier.job_id == job_id)
    return query.order_by(OptionRouteStop.sequence_index).all()


@router.get("/couriers/me/jobs", response_model=list[CourierJobOut])
def list_my_jobs(
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    """The published jobs this courier has stops in — same hard filter as the
    assignment query (published-only, self-only via the authenticated user).
    """
    rows = (
        db.query(Job, JobCourier, OptionRouteStop.id)
        .join(JobCourier, JobCourier.job_id == Job.id)
        .join(OptionCourierRoute, OptionCourierRoute.job_courier_id == JobCourier.id)
        .join(Option, OptionCourierRoute.option_id == Option.id)
        .join(OptionRouteStop, OptionRouteStop.option_courier_route_id == OptionCourierRoute.id)
        .join(JobStop, OptionRouteStop.job_stop_id == JobStop.id)
        .filter(
            Option.status == OptionStatus.PUBLISHED,
            JobCourier.courier_id == courier.id,
            JobStop.deleted_at.is_(None),
        )
        .all()
    )
    counts: dict[str, list] = {}
    for job, jc, _route_stop_id in rows:
        counts.setdefault(job.id, [job, jc, 0])
        counts[job.id][2] += 1
    entries = sorted(
        counts.values(),
        key=lambda item: item[0].delivery_date or date.min,
        reverse=True,  # newest delivery date first; date-less legacy days last
    )
    return [
        CourierJobOut(
            job_id=job.id,
            delivery_date=job.delivery_date,
            stop_count=count,
            **{f: getattr(jc, f) for f in LOCATION_FIELDS},
        )
        for job, jc, count in entries
    ]


@router.get("/couriers/me/assignments", response_model=list[AssignmentStopOut])
def list_my_assignments(
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    rows = _assignment_query(db, courier.id)
    return [
        AssignmentStopOut(
            job_stop_id=stop.id, address_label=stop.address_label, lat=stop.lat, lon=stop.lon,
            sequence_index=route_stop.sequence_index,
        )
        for route_stop, stop in rows
    ]


@router.get("/couriers/me/assignments/{job_id}", response_model=list[AssignmentStopOut])
def get_my_assignment_for_job(
    job_id: str,
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    rows = _assignment_query(db, courier.id, job_id=job_id)
    if not rows:
        # 404, not empty array — avoids confirming a job's existence to a
        # courier with no relationship to it.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return [
        AssignmentStopOut(
            job_stop_id=stop.id, address_label=stop.address_label, lat=stop.lat, lon=stop.lon,
            sequence_index=route_stop.sequence_index,
        )
        for route_stop, stop in rows
    ]
