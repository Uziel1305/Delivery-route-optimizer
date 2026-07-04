from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import CourierProfile, User, UserRole
from app.auth.dependencies import require_role
from app.couriers.models import CourierInvite, InviteStatus, LocationChangeRequest, LocationRequestStatus
from app.couriers.schemas import (
    CourierLocationsOut,
    CourierOut,
    InviteCreateRequest,
    InviteOut,
    LocationRequestOut,
    LocationRequestWithCourierOut,
    MyManagerOut,
    RosterCourierOut,
    SetLocationsRequest,
    SetLocationsResponse,
)
from app.database import get_db

router = APIRouter(tags=["couriers"])

LOCATION_FIELDS = ("start_lat", "start_lon", "start_address_label", "end_lat", "end_lon", "end_address_label")


def _apply_locations(profile: CourierProfile, source) -> None:
    for f in LOCATION_FIELDS:
        setattr(profile, f, getattr(source, f))


def _pending_request_for(db: Session, courier_id: str) -> LocationChangeRequest | None:
    return (
        db.query(LocationChangeRequest)
        .filter(
            LocationChangeRequest.courier_id == courier_id,
            LocationChangeRequest.status == LocationRequestStatus.PENDING,
        )
        .first()
    )


@router.get("/managers/me/courier-suggestions", response_model=list[CourierOut])
def suggest_couriers(
    q: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    """Typeahead for the invite form. Only surfaces couriers who are
    actually invitable right now — no manager yet, and no pending invite
    already out from this manager — so a suggestion never leads to a 409.
    """
    if not q.strip():
        return []
    pending_courier_ids = (
        db.query(CourierInvite.courier_id)
        .filter(CourierInvite.manager_id == manager.id, CourierInvite.status == InviteStatus.PENDING)
        .subquery()
    )
    return (
        db.query(User)
        .join(CourierProfile, CourierProfile.user_id == User.id)
        .filter(
            User.role == UserRole.COURIER,
            User.username.ilike(f"%{q}%"),
            CourierProfile.manager_id.is_(None),
            User.id.not_in(pending_courier_ids),
        )
        .order_by(User.username)
        .limit(8)
        .all()
    )


@router.post("/managers/me/invites", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
def send_invite(
    payload: InviteCreateRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    courier = (
        db.query(User)
        .filter(User.username == payload.courier_username, User.role == UserRole.COURIER)
        .first()
    )
    if courier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="courier not found")

    profile = db.get(CourierProfile, courier.id)
    if profile is not None and profile.manager_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="courier_already_assigned")

    existing_pending = (
        db.query(CourierInvite)
        .filter(
            CourierInvite.manager_id == manager.id,
            CourierInvite.courier_id == courier.id,
            CourierInvite.status == InviteStatus.PENDING,
        )
        .first()
    )
    if existing_pending is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invite already pending")

    invite = CourierInvite(manager_id=manager.id, courier_id=courier.id, status=InviteStatus.PENDING)
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@router.get("/managers/me/invites", response_model=list[InviteOut])
def list_sent_invites(
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    return db.query(CourierInvite).filter(CourierInvite.manager_id == manager.id).all()


@router.delete("/managers/me/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_invite(
    invite_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    invite = (
        db.query(CourierInvite)
        .filter(CourierInvite.id == invite_id, CourierInvite.manager_id == manager.id)
        .first()
    )
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if invite.status != InviteStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invite is not pending")

    invite.status = InviteStatus.CANCELLED
    db.commit()


@router.get("/couriers/me/manager", response_model=MyManagerOut)
def get_my_manager(
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    profile = db.get(CourierProfile, courier.id)
    if profile is None or profile.manager_id is None:
        return MyManagerOut(manager_id=None, manager_username=None)
    manager = db.get(User, profile.manager_id)
    return MyManagerOut(
        manager_id=profile.manager_id,
        manager_username=manager.username if manager else None,
    )


@router.get("/couriers/me/invites", response_model=list[InviteOut])
def list_received_invites(
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    return (
        db.query(CourierInvite)
        .filter(CourierInvite.courier_id == courier.id, CourierInvite.status == InviteStatus.PENDING)
        .all()
    )


@router.post("/couriers/me/invites/{invite_id}/accept", response_model=InviteOut)
def accept_invite(
    invite_id: str,
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    invite = (
        db.query(CourierInvite)
        .filter(CourierInvite.id == invite_id, CourierInvite.courier_id == courier.id)
        .first()
    )
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if invite.status != InviteStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invite is not pending")

    profile = db.get(CourierProfile, courier.id)
    if profile is None:
        profile = CourierProfile(user_id=courier.id)
        db.add(profile)
    if profile.manager_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="courier_already_assigned")

    now = datetime.now(timezone.utc)
    invite.status = InviteStatus.ACCEPTED
    invite.responded_at = now
    profile.manager_id = invite.manager_id

    # Handles the race of multiple managers inviting the same free courier.
    other_pending = (
        db.query(CourierInvite)
        .filter(
            CourierInvite.courier_id == courier.id,
            CourierInvite.status == InviteStatus.PENDING,
            CourierInvite.id != invite.id,
        )
        .all()
    )
    for other in other_pending:
        other.status = InviteStatus.REJECTED
        other.responded_at = now

    db.commit()
    db.refresh(invite)
    return invite


@router.post("/couriers/me/invites/{invite_id}/reject", response_model=InviteOut)
def reject_invite(
    invite_id: str,
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    invite = (
        db.query(CourierInvite)
        .filter(CourierInvite.id == invite_id, CourierInvite.courier_id == courier.id)
        .first()
    )
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if invite.status != InviteStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invite is not pending")

    invite.status = InviteStatus.REJECTED
    invite.responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invite)
    return invite


@router.post("/couriers/me/leave-manager", status_code=status.HTTP_204_NO_CONTENT)
def leave_manager(
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    """Without this, a courier accepted by one manager would have no way to
    ever leave — only the manager could remove them.
    """
    profile = db.get(CourierProfile, courier.id)
    if profile is None or profile.manager_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="courier has no manager")
    profile.manager_id = None
    db.commit()


@router.get("/managers/me/couriers", response_model=list[RosterCourierOut])
def list_roster(
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(User, CourierProfile)
        .join(CourierProfile, CourierProfile.user_id == User.id)
        .filter(CourierProfile.manager_id == manager.id)
        .all()
    )
    result = []
    for user, profile in rows:
        pending = _pending_request_for(db, user.id)
        result.append(
            RosterCourierOut(
                id=user.id,
                username=user.username,
                email=user.email,
                has_locations=profile.has_locations,
                start_lat=profile.start_lat,
                start_lon=profile.start_lon,
                start_address_label=profile.start_address_label,
                end_lat=profile.end_lat,
                end_lon=profile.end_lon,
                end_address_label=profile.end_address_label,
                pending_request=LocationRequestOut.model_validate(pending) if pending else None,
            )
        )
    return result


@router.delete("/managers/me/couriers/{courier_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_courier(
    courier_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(CourierProfile)
        .filter(CourierProfile.user_id == courier_id, CourierProfile.manager_id == manager.id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    profile.manager_id = None
    db.commit()


# --- Courier start/end locations & the manager-consent change flow ---------


@router.get("/couriers/me/locations", response_model=CourierLocationsOut)
def get_my_locations(
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    profile = db.get(CourierProfile, courier.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="courier profile missing")
    pending = _pending_request_for(db, courier.id)
    return CourierLocationsOut(
        has_locations=profile.has_locations,
        start_lat=profile.start_lat,
        start_lon=profile.start_lon,
        start_address_label=profile.start_address_label,
        end_lat=profile.end_lat,
        end_lon=profile.end_lon,
        end_address_label=profile.end_address_label,
        pending_request=LocationRequestOut.model_validate(pending) if pending else None,
    )


@router.put("/couriers/me/locations", response_model=SetLocationsResponse)
def set_my_locations(
    payload: SetLocationsRequest,
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    """First-time onboarding always applies directly (a manager can't plan
    with a location-less courier anyway). After that: unaffiliated couriers
    apply directly; managed couriers create a pending approval request.
    """
    profile = db.get(CourierProfile, courier.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="courier profile missing")

    if profile.manager_id is None or not profile.has_locations:
        _apply_locations(profile, payload)
        db.commit()
        return SetLocationsResponse(applied=True, pending_request=None)

    if _pending_request_for(db, courier.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a change request is already pending")

    request = LocationChangeRequest(
        courier_id=courier.id,
        start_lat=payload.start_lat,
        start_lon=payload.start_lon,
        start_address_label=payload.start_address_label,
        end_lat=payload.end_lat,
        end_lon=payload.end_lon,
        end_address_label=payload.end_address_label,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return SetLocationsResponse(applied=False, pending_request=LocationRequestOut.model_validate(request))


@router.delete("/couriers/me/locations/pending", status_code=status.HTTP_204_NO_CONTENT)
def cancel_my_pending_location_request(
    courier: User = Depends(require_role(UserRole.COURIER)),
    db: Session = Depends(get_db),
):
    pending = _pending_request_for(db, courier.id)
    if pending is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no pending request")
    pending.status = LocationRequestStatus.CANCELLED
    pending.resolved_at = datetime.now(timezone.utc)
    db.commit()


def _get_managed_request(db: Session, request_id: str, manager: User) -> LocationChangeRequest:
    """Ownership re-verified against the DB: the request's courier must
    currently belong to this manager (never trust ids from the path alone).
    """
    request = db.get(LocationChangeRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    profile = db.get(CourierProfile, request.courier_id)
    if profile is None or profile.manager_id != manager.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if request.status != LocationRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="request is not pending")
    return request


@router.get("/managers/me/location-requests", response_model=list[LocationRequestWithCourierOut])
def list_location_requests(
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(LocationChangeRequest, User.username)
        .join(CourierProfile, CourierProfile.user_id == LocationChangeRequest.courier_id)
        .join(User, User.id == LocationChangeRequest.courier_id)
        .filter(
            CourierProfile.manager_id == manager.id,
            LocationChangeRequest.status == LocationRequestStatus.PENDING,
        )
        .order_by(LocationChangeRequest.created_at)
        .all()
    )
    return [
        LocationRequestWithCourierOut(
            **LocationRequestOut.model_validate(request).model_dump(),
            courier_username=username,
        )
        for request, username in rows
    ]


@router.post("/managers/me/location-requests/{request_id}/approve", response_model=LocationRequestOut)
def approve_location_request(
    request_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    request = _get_managed_request(db, request_id, manager)
    profile = db.get(CourierProfile, request.courier_id)
    _apply_locations(profile, request)
    request.status = LocationRequestStatus.APPROVED
    request.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)
    return request


@router.post("/managers/me/location-requests/{request_id}/decline", response_model=LocationRequestOut)
def decline_location_request(
    request_id: str,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    request = _get_managed_request(db, request_id, manager)
    request.status = LocationRequestStatus.DECLINED
    request.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)
    return request


@router.put("/managers/me/couriers/{courier_id}/locations", response_model=CourierLocationsOut)
def set_courier_locations(
    courier_id: str,
    payload: SetLocationsRequest,
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    """Direct manager edit of a courier's default locations. Supersedes any
    pending change request from the courier (marked cancelled).
    """
    profile = (
        db.query(CourierProfile)
        .filter(CourierProfile.user_id == courier_id, CourierProfile.manager_id == manager.id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    _apply_locations(profile, payload)
    pending = _pending_request_for(db, courier_id)
    if pending is not None:
        pending.status = LocationRequestStatus.CANCELLED
        pending.resolved_at = datetime.now(timezone.utc)
    db.commit()

    return CourierLocationsOut(
        has_locations=profile.has_locations,
        start_lat=profile.start_lat,
        start_lon=profile.start_lon,
        start_address_label=profile.start_address_label,
        end_lat=profile.end_lat,
        end_lon=profile.end_lon,
        end_address_label=profile.end_address_label,
        pending_request=None,
    )
