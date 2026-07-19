import enum
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"      # заявка с сайта, ждёт подтверждения
    CONFIRMED = "CONFIRMED"  # админ подтвердил
    BLOCKED = "BLOCKED"      # админ занял вручную


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(100))
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hourly_rate: Mapped[int] = mapped_column(Integer)   # ₽/час
    deposit: Mapped[int] = mapped_column(Integer)       # залог, ₽
    specs: Mapped[dict] = mapped_column(JSONB)          # ТТХ: разный набор у разной техники
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="equipment")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"))

    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)

    address: Mapped[str] = mapped_column(String(500))
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_phone: Mapped[str] = mapped_column(String(50))

    logistics_cost: Mapped[int] = mapped_column(Integer, default=0)  # ₽ за доставку
    
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"), default=BookingStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    equipment: Mapped["Equipment"] = relationship(back_populates="bookings")


# ускоряет проверку пересечений
Index("ix_bookings_equipment_period", Booking.equipment_id, Booking.start_at, Booking.end_at)