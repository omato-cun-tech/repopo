from datetime import datetime, date, time
from typing import Optional, List
from sqlalchemy import BigInteger, String, Integer, Boolean, Float, Date, Time, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.database import Base
import enum

class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELED = "canceled"
    NO_SHOW = "no_show"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))
    bonus_balance: Mapped[int] = mapped_column(Integer, default=0)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    registered_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    referred_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)
    duration: Mapped[int] = mapped_column(Integer, comment="Duration in minutes")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Slot(Base):
    __tablename__ = "slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    time: Mapped[time] = mapped_column(Time)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    appointment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)

class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    status: Mapped[AppointmentStatus] = mapped_column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING)
    total_price: Mapped[float] = mapped_column(Float)
    bonuses_used: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship("User")
    service: Mapped["Service"] = relationship("Service")
    # Explicitly specify foreign_keys to resolve ambiguity
    slot: Mapped["Slot"] = relationship("Slot", foreign_keys=[slot_id])
    all_slots: Mapped[List["Slot"]] = relationship("Slot", foreign_keys=[Slot.appointment_id], back_populates="appointment")

# Update Slot to have back_populates
Slot.appointment = relationship("Appointment", foreign_keys=[Slot.appointment_id], back_populates="all_slots")
