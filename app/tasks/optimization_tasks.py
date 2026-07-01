from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.jobs.models import CourierCountMode, Job, JobCourier, JobStatus, JobStop, Option
from app.optimization import solver
from app.optimization.matrix.osrm_provider import OsrmTimeMatrixProvider
from app.optimization.models import Coordinate, Depot, Stop
from app.services.optimization_adapter import build_problem_instance, persist_solution
from app.tasks.celery_app import celery_app

settings = get_settings()


def run_generation(
    db: Session,
    job: Job,
    courier_count: int | None = None,
    parent_option_id: str | None = None,
) -> Option | None:
    """Core generation logic. Called synchronously by the jobs router in
    this scaffold; also wrapped as a Celery task below for true async
    dispatch to a worker if request-time solve times become too long.

    Returns None if infeasible for the requested courier_count (or, when
    courier_count is None, infeasible with the full pool).
    """
    job_couriers = db.query(JobCourier).filter(JobCourier.job_id == job.id).all()
    active_stops = db.query(JobStop).filter(JobStop.job_id == job.id, JobStop.deleted_at.is_(None)).all()

    depot = Depot(coordinate=Coordinate(lat=job.depot_lat, lon=job.depot_lon))
    opt_stops = tuple(
        Stop(id=s.id, coordinate=Coordinate(lat=s.lat, lon=s.lon), service_time_seconds=s.service_time_seconds)
        for s in active_stops
    )
    matrix_provider = OsrmTimeMatrixProvider(base_url=settings.osrm_base_url)
    time_matrix = matrix_provider.get_matrix(depot, opt_stops)

    instance = build_problem_instance(job, job_couriers, active_stops, time_matrix)

    if courier_count is None:
        result = solver.solve(instance)
        requested_n = None
        mode = None
        if not result.feasible:
            return None
    else:
        result = solver.solve_with_courier_count(instance, courier_count)
        requested_n = courier_count
        mode = CourierCountMode.EXACT
        if result is None:
            return None

    option = persist_solution(db, job, requested_n, mode, result, active_stops, parent_option_id=parent_option_id)

    job.status = JobStatus.OPTIONS_READY
    db.commit()
    return option


@celery_app.task(name="run_optimization_task")
def run_optimization_task(job_id: str, courier_count: int | None = None) -> str | None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return None
        option = run_generation(db, job, courier_count=courier_count)
        return option.id if option else None
    finally:
        db.close()
