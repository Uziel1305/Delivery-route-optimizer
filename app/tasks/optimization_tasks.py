import logging

# The worker process doesn't import the API routers, so pull in every model
# module explicitly: flushing a Job UPDATE makes SQLAlchemy resolve
# jobs.manager_id -> users.id, which fails with NoReferencedTableError unless
# the users table is registered in this process's metadata.
import app.auth.models  # noqa: F401
import app.couriers.models  # noqa: F401
from app.config import get_settings
from app.database import SessionLocal
from app.jobs.models import Job, JobCourier, JobStatus, JobStop, Option, OptionStatus
from app.optimization import solver
from app.optimization.matrix.osrm_provider import OsrmTimeMatrixProvider
from app.services.optimization_adapter import (
    MissingCourierLocations,
    build_opt_couriers,
    build_opt_stops,
    build_problem_instance,
    fill_option,
    snapshot_hash,
)
from app.tasks.celery_app import celery_app

settings = get_settings()
logger = logging.getLogger(__name__)


@celery_app.task(name="run_optimization_task")
def run_optimization_task(option_id: str) -> str | None:
    """Solve a PENDING option in the worker and fill it in place.

    Terminal states — a dispatched option never stays PENDING:
      - ACTIVE: solved; job flips to OPTIONS_READY.
      - STALE: solved, but the day's stops/terminals changed mid-solve
        (snapshot hash mismatch) — routes are stored but not trusted.
      - FAILED: infeasible, missing courier locations, or unexpected error;
        the human-readable reason goes to Option.error_detail.
    """
    db = SessionLocal()
    try:
        option = db.get(Option, option_id)
        if option is None or option.status != OptionStatus.PENDING:
            return None
        job = db.get(Job, option.job_id)
        if job is None:
            _fail(db, option, "delivery day no longer exists")
            return None

        try:
            return _solve_into(db, job, option)
        except MissingCourierLocations:
            _fail(
                db,
                option,
                "couriers on this day have no start/end locations "
                "(created before per-courier locations) — recreate the delivery day",
            )
            return None
        except Exception:
            logger.exception("optimization task failed for option %s", option_id)
            _fail(db, option, "internal error while generating routes — try again")
            return None
    finally:
        db.close()


def _solve_into(db, job: Job, option: Option) -> str | None:
    job_couriers = db.query(JobCourier).filter(JobCourier.job_id == job.id).all()
    active_stops = db.query(JobStop).filter(JobStop.job_id == job.id, JobStop.deleted_at.is_(None)).all()

    matrix_provider = OsrmTimeMatrixProvider(base_url=settings.osrm_base_url)
    time_matrix = matrix_provider.get_matrix(build_opt_couriers(job_couriers), build_opt_stops(active_stops))
    instance = build_problem_instance(job_couriers, active_stops, time_matrix)

    if option.requested_courier_count is None:
        result = solver.solve(instance)
        if not result.feasible:
            _fail(db, option, "infeasible with the full courier pool")
            return None
    else:
        result = solver.solve_with_courier_count(instance, option.requested_courier_count)
        if result is None:
            _fail(db, option, f"not feasible with exactly {option.requested_courier_count} courier(s)")
            return None

    # Day edited while we were solving? Store the routes but mark them STALE
    # so the manager sees they predate the edit; don't touch job.status.
    if snapshot_hash(active_stops, job_couriers) != option.stops_snapshot_hash:
        fill_option(db, option, result, final_status=OptionStatus.STALE)
        return option.id

    # Set job.status BEFORE fill_option so its commit covers both — a poller
    # must never observe an ACTIVE option on a still-DRAFT job.
    job.status = JobStatus.OPTIONS_READY
    fill_option(db, option, result)
    return option.id


def _fail(db, option: Option, detail: str) -> None:
    option.status = OptionStatus.FAILED
    option.error_detail = detail
    db.commit()
