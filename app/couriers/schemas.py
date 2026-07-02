from pydantic import BaseModel

from app.couriers.models import InviteStatus


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
