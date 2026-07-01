from pydantic import BaseModel

from app.jobs.models import CourierCountMode, JobStatus, OptionStatus


class JobCourierIn(BaseModel):
    courier_id: str
    start_time_seconds: int
    end_time_seconds: int


class JobCreateRequest(BaseModel):
    depot_lat: float
    depot_lon: float
    couriers: list[JobCourierIn]


class JobOut(BaseModel):
    id: str
    manager_id: str
    status: JobStatus
    published_option_id: str | None

    model_config = {"from_attributes": True}


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
    parent_option_id: str | None
    courier_routes: list[CourierRouteOut]
    unassigned_stop_ids: list[str]


class GenerateInfeasibleResponse(BaseModel):
    detail: str
    existing_options: list[OptionOut]


class SwapRequest(BaseModel):
    job_stop_id: str
    to_job_courier_id: str


class AssignmentStopOut(BaseModel):
    job_stop_id: str
    address_label: str
    lat: float
    lon: float
    sequence_index: int
