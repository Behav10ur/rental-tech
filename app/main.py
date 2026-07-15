from datetime import datetime
from app.admin import router as admin_router

from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Equipment, Booking, BookingStatus
from app.booking_service import busy_intervals, validate_slot
from app.rules import MIN_HOURS

app = FastAPI(title="Аренда спецтехники")
app.include_router(admin_router)
templates = Jinja2Templates(directory="app/templates")


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

    return templates.TemplateResponse(
        request,
        "equipment.html",
        {
            "item": item,
            "busy": busy_intervals(db, equipment_id),
            "error": None,
            "success": None,
            "min_hours": MIN_HOURS,
        },
    )


@app.post("/equipment/{equipment_id}/book", response_class=HTMLResponse)
def create_booking(
    equipment_id: int,
    request: Request,
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

    def render(error=None, success=None):
        return templates.TemplateResponse(
            request,
            "equipment.html",
            {
                "item": item,
                "busy": busy_intervals(db, equipment_id),
                "error": error,
                "success": success,
                "min_hours": MIN_HOURS,
            },
        )

    if not agree:
        return render(error="Нужно согласие на обработку персональных данных.")

    try:
        start_at = datetime.fromisoformat(f"{date}T{time_from}")
        end_at = datetime.fromisoformat(f"{date}T{time_to}")
    except ValueError:
        return render(error="Некорректная дата или время.")

    error = validate_slot(db, equipment_id, start_at, end_at)
    if error:
        return render(error=error)

    db.add(
        Booking(
            equipment_id=equipment_id,
            start_at=start_at,
            end_at=end_at,
            address=address.strip(),
            customer_name=name.strip(),
            customer_phone=phone.strip(),
            status=BookingStatus.PENDING,
        )
    )
    db.commit()

    return render(success="Заявка отправлена! Мы свяжемся с вами.")