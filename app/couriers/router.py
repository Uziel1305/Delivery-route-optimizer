from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import CourierProfile, User, UserRole
from app.auth.dependencies import require_role
from app.couriers.models import CourierInvite, InviteStatus
from app.couriers.schemas import CourierOut, InviteCreateRequest, InviteOut, MyManagerOut
from app.database import get_db

router = APIRouter(tags=["couriers"])


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


@router.get("/managers/me/couriers", response_model=list[CourierOut])
def list_roster(
    manager: User = Depends(require_role(UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    return (
        db.query(User)
        .join(CourierProfile, CourierProfile.user_id == User.id)
        .filter(CourierProfile.manager_id == manager.id)
        .all()
    )


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
