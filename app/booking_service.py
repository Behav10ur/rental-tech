import math
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus, Equipment
from app.rules import MIN_HOURS, BUFFER_MINUTES, WORK_START_HOUR, WORK_END_HOUR

# статусы, которые реально занимают технику (PENDING — не занимает)
BLOCKING_STATUSES = (BookingStatus.CONFIRMED, BookingStatus.BLOCKED)


def busy_intervals(db: Session, equipment_id: int) -> list[Booking]:
    """Занятые интервалы техники: подтверждённые + заблокированные, только будущие."""
    stmt = (
        select(Booking)
        .where(
            Booking.equipment_id == equipment_id,
            Booking.status.in_(BLOCKING_STATUSES),
            Booking.end_at >= datetime.now(),
        )
        .order_by(Booking.start_at)
    )
    return list(db.scalars(stmt))


def validate_slot(db: Session, equipment_id: int, start_at: datetime, end_at: datetime) -> str | None:
    """Проверяет слот. Возвращает текст ошибки или None, если всё ок."""
    if end_at <= start_at:
        return "Время окончания должно быть позже начала."

    if start_at < datetime.now():
        return "Нельзя забронировать время в прошлом."

    hours = (end_at - start_at).total_seconds() / 3600
    if hours < MIN_HOURS:
        return f"Минимальное время аренды — {MIN_HOURS} часа."

    # рабочее окно
    end_hour = end_at.hour + (1 if end_at.minute > 0 else 0)
    if start_at.hour < WORK_START_HOUR or end_hour > WORK_END_HOUR:
        return f"Бронирование доступно с {WORK_START_HOUR}:00 до {WORK_END_HOUR}:00."

    if not db.get(Equipment, equipment_id):
        return "Техника не найдена."

    # симметричный буфер: раздуваем окно на час в обе стороны
    buffer = timedelta(minutes=BUFFER_MINUTES)
    window_start = start_at - buffer
    window_end = end_at + buffer

    conflict = db.scalar(
        select(Booking).where(
            Booking.equipment_id == equipment_id,
            Booking.status.in_(BLOCKING_STATUSES),
            Booking.start_at < window_end,   # классическая формула пересечения
            Booking.end_at > window_start,
        )
    )
    if conflict:
        return "Это время уже занято (с учётом времени на обслуживание). Выберите другой интервал."

    return None

def billed_hours(start_at: datetime, end_at: datetime) -> int:
    """Часы к оплате: неполный час округляется вверх."""
    raw = (end_at - start_at).total_seconds() / 3600
    return math.ceil(raw)


def booking_cost(equipment: Equipment, start_at: datetime, end_at: datetime) -> dict:
    """Разбивка стоимости брони."""
    hours = billed_hours(start_at, end_at)
    rent = hours * equipment.hourly_rate
    return {
        "hours": hours,
        "rent": rent,
        "deposit": equipment.deposit,
        "total": rent + equipment.deposit,
    }