from datetime import datetime

from pydantic import BaseModel

from app.couriers.models import InviteStatus, LocationRequestStatus


class InviteCreateRequest(BaseModel):
    courier_username: str


class InviteOut(BaseModel):
    id: str
    manager_id: str
    courier_id: str
    status: InviteStatus

    model_config = {"from_attributes": True}


class CourierOut(BaseModel):
    id: str
    username: str
    email: str

    model_config = {"from_attributes": True}


class MyManagerOut(BaseModel):
    manager_id: str | None
    manager_username: str | None


class SetLocationsRequest(BaseModel):
    start_lat: float
    start_lon: float
    start_address_label: str
    end_lat: float
    end_lon: float
    end_address_label: str


class LocationRequestOut(BaseModel):
    id: str
    courier_id: str
    start_lat: float
    start_lon: float
    start_address_label: str
    end_lat: float
    end_lon: float
    end_address_label: str
    status: LocationRequestStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class LocationRequestWithCourierOut(LocationRequestOut):
    courier_username: str


class CourierLocationsOut(BaseModel):
    has_locations: bool
    start_lat: float | None
    start_lon: float | None
    start_address_label: str | None
    end_lat: float | None
    end_lon: float | None
    end_address_label: str | None
    pending_request: LocationRequestOut | None


class SetLocationsResponse(BaseModel):
    applied: bool  # False = a pending approval request was created instead
    pending_request: LocationRequestOut | None


class RosterCourierOut(CourierOut):
    """Roster row enriched with the courier's default locations and any
    pending change request, so the Roster screen needs a single call.
    """
    has_locations: bool
    start_lat: float | None
    start_lon: float | None
    start_address_label: str | None
    end_lat: float | None
    end_lon: float | None
    end_address_label: str | None
    pending_request: LocationRequestOut | None
