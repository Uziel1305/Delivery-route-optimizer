from datetime import date, datetime

from pydantic import BaseModel

from app.jobs.models import CourierCountMode, JobStatus, OptionStatus


class JobCourierIn(BaseModel):
    courier_id: str
    start_time_seconds: int
    end_time_seconds: int


class JobCreateRequest(BaseModel):
    delivery_date: date
    couriers: list[JobCourierIn]


class JobOut(BaseModel):
    id: str
    manager_id: str
    status: JobStatus
    published_option_id: str | None
    delivery_date: date | None

    model_config = {"from_attributes": True}


class JobSummaryOut(BaseModel):
    id: str
    status: JobStatus
    published_option_id: str | None
    delivery_date: date | None
    stop_count: int
    courier_count: int


class JobDetailOut(BaseModel):
    id: str
    status: JobStatus
    published_option_id: str | None
    delivery_date: date | None


class JobCourierOut(BaseModel):
    job_courier_id: str
    courier_id: str
    username: str
    start_time_seconds: int
    end_time_seconds: int
    # This day's route terminals (copy-on-assign; nullable only on legacy rows).
    start_lat: float | None
    start_lon: float | None
    start_address_label: str | None
    end_lat: float | None
    end_lon: float | None
    end_address_label: str | None


class JobCourierLocationsUpdateRequest(BaseModel):
    """Day-only edit of one courier's route terminals on this delivery day."""
    start_lat: float
    start_lon: float
    start_address_label: str
    end_lat: float
    end_lon: float
    end_address_label: str


class CourierJobOut(BaseModel):
    job_id: str
    delivery_date: date | None
    start_lat: float | None
    start_lon: float | None
    start_address_label: str | None
    end_lat: float | None
    end_lon: float | None
    end_address_label: str | None
    stop_count: int


class StopCreateRequest(BaseModel):
    lat: float
    lon: float
    service_time_seconds: int = 0
    address_label: str


class StopOut(BaseModel):
    id: str
    lat: float
    lon: float
    service_time_seconds: int
    address_label: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateWithNRequest(BaseModel):
    courier_count: int


class RouteStopOut(BaseModel):
    job_stop_id: str
    sequence_index: int
    leg_travel_seconds: float


class CourierRouteOut(BaseModel):
    job_courier_id: str
    total_travel_seconds: float
    total_service_seconds: float
    total_duration_seconds: float
    stops: list[RouteStopOut]


class OptionOut(BaseModel):
    id: str
    job_id: str
    label: str
    requested_courier_count: int | None
    courier_count_mode: CourierCountMode | None
    algorithm_key: str
    algorithm_tier: str
    total_duration_seconds: float
    feasible: bool
    status: OptionStatus
    error_detail: str | None = None
    parent_option_id: str | None
    courier_routes: list[CourierRouteOut]
    unassigned_stop_ids: list[str]


class SwapRequest(BaseModel):
    job_stop_id: str
    to_job_courier_id: str


class AssignmentStopOut(BaseModel):
    job_stop_id: str
    address_label: str
    lat: float
    lon: float
    sequence_index: int


class SavedLocationCreateRequest(BaseModel):
    lat: float
    lon: float
    service_time_seconds: int = 0
    address_label: str


class SavedLocationOut(BaseModel):
    id: str
    lat: float
    lon: float
    service_time_seconds: int
    address_label: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AddStopsFromLocationsRequest(BaseModel):
    location_ids: list[str]
