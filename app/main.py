from datetime import datetime
from app.rules import MIN_HOURS, WORK_START_HOUR, WORK_END_HOUR

from fastapi.responses import JSONResponse
from app.geo import logistics_for_address

from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Equipment, Booking, BookingStatus
from app.booking_service import busy_intervals, validate_slot
from app.flash import set_flash, pop_flash
from app.admin import router as admin_router

app = FastAPI(title="Аренда спецтехники")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["current_year"] = datetime.now().year

app.include_router(admin_router)


@app.get("/", response_class=HTMLResponse)
def catalog(request: Request, db: Session = Depends(get_db)):
    items = list(db.scalars(select(Equipment).order_by(Equipment.id)))
    return templates.TemplateResponse(request, "catalog.html", {"items": items})


@app.get("/equipment/{equipment_id}", response_class=HTMLResponse)
def equipment_page(
    equipment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    item = db.get(Equipment, equipment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Техника не найдена")

    flash = pop_flash(request)
    response = templates.TemplateResponse(
        request,
        "equipment.html",
        {
            "item": item,
            "busy": busy_intervals(db, equipment_id),
            "error": flash["message"] if flash and flash["category"] == "error" else None,
            "success": flash["message"] if flash and flash["category"] == "success" else None,
            "min_hours": MIN_HOURS,
            "work_start": WORK_START_HOUR,
            "work_end": WORK_END_HOUR,
        },
    )
    response.delete_cookie("flash")
    return response

@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {})

@app.post("/api/logistics")
def calc_logistics(address: str = Form(...)):
    result = logistics_for_address(address.strip())
    return JSONResponse(result)

@app.post("/equipment/{equipment_id}/book")
def create_booking(
    equipment_id: int,
    db: Session = Depends(get_db),
    date: str = Form(...),
    time_from: str = Form(...),
    time_to: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    agree: str | None = Form(None),
):
    item = db.get(Equipment, equipment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Техника не найдена")

    redirect = RedirectResponse(f"/equipment/{equipment_id}", status_code=303)

    if not agree:
        set_flash(redirect, "error", "Нужно согласие на обработку персональных данных.")
        return redirect

    try:
        start_at = datetime.fromisoformat(f"{date}T{time_from}")
        end_at = datetime.fromisoformat(f"{date}T{time_to}")
    except ValueError:
        set_flash(redirect, "error", "Некорректная дата или время.")
        return redirect

    error = validate_slot(db, equipment_id, start_at, end_at)
    if error:
        set_flash(redirect, "error", error)
        return redirect

    # пересчитываем логистику на сервере (не доверяем полю из формы)
    logistics = logistics_for_address(address.strip())
    if not logistics["ok"]:
        set_flash(redirect, "error", logistics["reason"])
        return redirect

    db.add(
        Booking(
            equipment_id=equipment_id,
            start_at=start_at,
            end_at=end_at,
            address=address.strip(),
            customer_name=name.strip(),
            customer_phone=phone.strip(),
            logistics_cost=logistics["cost"],
            status=BookingStatus.PENDING,
        )
    )
    db.commit()

    set_flash(redirect, "success", "Заявка отправлена! Мы свяжемся с вами.")
    return redirect