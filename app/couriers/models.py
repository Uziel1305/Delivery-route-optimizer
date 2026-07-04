import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InviteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LocationRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class LocationChangeRequest(Base):
    """A managed courier's proposed change to their default start/end
    locations, awaiting their manager's approval. Unaffiliated couriers
    never create one — their edits apply immediately. At most one PENDING
    row per courier (enforced in the endpoint).
    """

    __tablename__ = "location_change_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    courier_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    start_lat: Mapped[float] = mapped_column(Float, nullable=False)
    start_lon: Mapped[float] = mapped_column(Float, nullable=False)
    start_address_label: Mapped[str] = mapped_column(String(255), nullable=False)
    end_lat: Mapped[float] = mapped_column(Float, nullable=False)
    end_lon: Mapped[float] = mapped_column(Float, nullable=False)
    end_address_label: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[LocationRequestStatus] = mapped_column(
        Enum(LocationRequestStatus), nullable=False, default=LocationRequestStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CourierInvite(Base):
    __tablename__ = "courier_invites"
    __table_args__ = (
        Index(
            "ix_one_pending_invite_per_pair",
            "manager_id",
            "courier_id",
            unique=True,
            # SQLAlchemy's Enum() column stores the Python member NAME
            # ("PENDING"), not .value ("pending") — must match here.
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    manager_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    courier_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[InviteStatus] = mapped_column(Enum(InviteStatus), nullable=False, default=InviteStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
