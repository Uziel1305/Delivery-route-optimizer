import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    MANAGER = "manager"
    COURIER = "courier"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    courier_profile: Mapped["CourierProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="CourierProfile.user_id",
    )


class CourierProfile(Base):
    """Only present for role == COURIER. A separate table (rather than a
    nullable column on User) keeps 'currently unaffiliated courier' a clean
    absence of relationship rather than an overloaded nullable FK.
    """

    __tablename__ = "courier_profiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    manager_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    default_start_time_seconds: Mapped[int] = mapped_column(Integer, default=8 * 3600)
    default_end_time_seconds: Mapped[int] = mapped_column(Integer, default=17 * 3600)

    user: Mapped["User"] = relationship(back_populates="courier_profile", foreign_keys=[user_id])
