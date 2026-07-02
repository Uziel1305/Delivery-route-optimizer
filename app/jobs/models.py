import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    OPTIONS_READY = "options_ready"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class OptionStatus(str, enum.Enum):
    ACTIVE = "active"
    STALE = "stale"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class CourierCountMode(str, enum.Enum):
    EXACT = "exact"
    MAX = "max"


def _uuid() -> str:
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    manager_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    depot_lat: Mapped[float] = mapped_column(Float, nullable=False)
    depot_lon: Mapped[float] = mapped_column(Float, nullable=False)
    # Nullable at the DB level so this migration is safe against any existing
    # rows; the API requires it on creation via JobCreateRequest instead.
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), nullable=False, default=JobStatus.DRAFT)
    published_option_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("options.id", use_alter=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stops: Mapped[list["JobStop"]] = relationship(back_populates="job", foreign_keys="JobStop.job_id")
    couriers: Mapped[list["JobCourier"]] = relationship(back_populates="job", foreign_keys="JobCourier.job_id")


class JobStop(Base):
    __tablename__ = "job_stops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    service_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    address_label: Mapped[str] = mapped_column(String(255), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped["Job"] = relationship(back_populates="stops", foreign_keys=[job_id])


class JobCourier(Base):
    __tablename__ = "job_couriers"
    __table_args__ = (UniqueConstraint("job_id", "courier_id", name="uq_job_courier"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    courier_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    start_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="couriers", foreign_keys=[job_id])


class Option(Base):
    __tablename__ = "options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="Option")
    requested_courier_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    courier_count_mode: Mapped[CourierCountMode | None] = mapped_column(Enum(CourierCountMode), nullable=True)
    algorithm_key: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    total_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    feasible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[OptionStatus] = mapped_column(Enum(OptionStatus), nullable=False, default=OptionStatus.ACTIVE)
    parent_option_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("options.id"), nullable=True)
    stops_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    courier_routes: Mapped[list["OptionCourierRoute"]] = relationship(back_populates="option")
    unassigned_stops: Mapped[list["OptionUnassignedStop"]] = relationship(back_populates="option")


class OptionCourierRoute(Base):
    __tablename__ = "option_courier_routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    option_id: Mapped[str] = mapped_column(String(36), ForeignKey("options.id"), nullable=False, index=True)
    job_courier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_couriers.id"), nullable=False, index=True
    )
    total_travel_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_service_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    option: Mapped["Option"] = relationship(back_populates="courier_routes")
    stops: Mapped[list["OptionRouteStop"]] = relationship(
        back_populates="courier_route", order_by="OptionRouteStop.sequence_index"
    )


class OptionRouteStop(Base):
    __tablename__ = "option_route_stops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    option_courier_route_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("option_courier_routes.id"), nullable=False, index=True
    )
    job_stop_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_stops.id"), nullable=False, index=True)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    leg_travel_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    courier_route: Mapped["OptionCourierRoute"] = relationship(back_populates="stops")


class OptionUnassignedStop(Base):
    __tablename__ = "option_unassigned_stops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    option_id: Mapped[str] = mapped_column(String(36), ForeignKey("options.id"), nullable=False, index=True)
    job_stop_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_stops.id"), nullable=False, index=True)

    option: Mapped["Option"] = relationship(back_populates="unassigned_stops")


class SavedLocation(Base):
    """A manager's reusable delivery-address book. Quick-adding one to a job
    just copies its fields into a new JobStop — no link is kept back to this
    row, so there's no "already added to this job" tracking.
    """

    __tablename__ = "saved_locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    manager_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    service_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    address_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
