from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Equipment, Booking, BookingStatus
from app.booking_service import validate_slot, booking_cost
from app.auth import COOKIE_NAME, make_session_token, is_admin, check_password

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def require_admin(request: Request):
    """Зависимость: пускает только с валидной кукой."""
    if not is_admin(request):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {"error": None})


@router.post("/login")
def login(request: Request, password: str = Form(...)):
    if not check_password(password):
        return templates.TemplateResponse(
            request, "admin_login.html", {"error": "Неверный пароль."}
        )
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        make_session_token(),
        httponly=True,        # недоступна из JS
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # неделя
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    bookings = list(
        db.scalars(
            select(Booking)
            .options(selectinload(Booking.equipment))
            .order_by(Booking.start_at)
        )
    )
    equipment = list(db.scalars(select(Equipment).order_by(Equipment.id)))

    # считаем стоимость для каждой брони
    rows = []
    for b in bookings:
        cost = booking_cost(b.equipment, b.start_at, b.end_at)
        rows.append({"booking": b, "cost": cost})

    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {"rows": rows, "equipment": equipment, "error": None, "success": None},
    )


@router.post("/bookings/{booking_id}/confirm")
def confirm_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404)

    # проверяем, не занял ли кто-то слот, пока заявка висела
    error = validate_slot(db, booking.equipment_id, booking.start_at, booking.end_at)
    if error:
        return RedirectResponse(f"/admin?error={error}", status_code=303)

    booking.status = BookingStatus.CONFIRMED
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/bookings/{booking_id}/delete")
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    booking = db.get(Booking, booking_id)
    if booking:
        db.delete(booking)
        db.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/bookings/manual")
def manual_booking(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
    equipment_id: int = Form(...),
    date: str = Form(...),
    time_from: str = Form(...),
    time_to: str = Form(...),
    address: str = Form(...),
):
    try:
        start_at = datetime.fromisoformat(f"{date}T{time_from}")
        end_at = datetime.fromisoformat(f"{date}T{time_to}")
    except ValueError:
        return RedirectResponse("/admin?error=Некорректная дата", status_code=303)

    error = validate_slot(db, equipment_id, start_at, end_at)
    if error:
        return RedirectResponse(f"/admin?error={error}", status_code=303)

    db.add(
        Booking(
            equipment_id=equipment_id,
            start_at=start_at,
            end_at=end_at,
            address=address.strip(),
            customer_name="—",
            customer_phone="—",
            status=BookingStatus.BLOCKED,
        )
    )
    db.commit()
    return RedirectResponse("/admin", status_code=303)