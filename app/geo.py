import os
import math
import httpx
from dotenv import load_dotenv

from app.rules import (
    ORIGIN_LAT, ORIGIN_LON,
    BELTWAY_RADIUS_KM, MAX_EXTRA_KM, PRICE_PER_KM,
)

load_dotenv()

DADATA_URL = "https://cleaner.dadata.ru/api/v1/clean/address"
_API_KEY = os.environ["DADATA_API_KEY"]
_SECRET_KEY = os.environ["DADATA_SECRET_KEY"]


def geocode(address: str) -> dict | None:
    """
    Адрес → dict с координатами, качеством и распознанным адресом.
    None при сетевой ошибке.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {_API_KEY}",
        "X-Secret": _SECRET_KEY,
    }
    try:
        resp = httpx.post(DADATA_URL, headers=headers, json=[address], timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    if not data:
        return None

    item = data[0]
    lat = item.get("geo_lat")
    lon = item.get("geo_lon")

    return {
        "lat": float(lat) if lat is not None else None,
        "lon": float(lon) if lon is not None else None,
        "qc_geo": item.get("qc_geo"),          # точность координат
        "unparsed": item.get("unparsed_parts"),# нераспознанные части
        "result": item.get("result"),          # распознанный адрес
    }

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние по прямой между двумя точками на Земле, км."""
    R = 6371  # радиус Земли, км
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def logistics_for_address(address: str) -> dict:
    """
    Считает логистику по адресу объекта.
      ok=True  → cost, distance_km, extra_km, recognized
      ok=False → reason
    """
    geo = geocode(address)
    if geo is None:
        return {"ok": False, "reason": "Сервис адресов недоступен. Попробуйте позже."}

    # координаты не определены до точки (qc_geo 4) или адрес не разобран
    if geo["qc_geo"] == 4 or geo["lat"] is None or geo["lon"] is None:
        return {
            "ok": False,
            "reason": "Не удалось точно определить адрес. Укажите населённый пункт и улицу подробнее.",
        }

    # часть адреса не распознана — вероятно, опечатка или лишнее
    if geo["unparsed"]:
        return {
            "ok": False,
            "reason": f"Адрес распознан не полностью (не понято: «{geo['unparsed']}»). Уточните его.",
        }

    distance = haversine_km(ORIGIN_LAT, ORIGIN_LON, geo["lat"], geo["lon"])

    if distance <= BELTWAY_RADIUS_KM:
        return {
            "ok": True, "cost": 0,
            "distance_km": round(distance, 1), "extra_km": 0,
            "recognized": geo["result"],
        }

    extra = distance - BELTWAY_RADIUS_KM
    if extra > MAX_EXTRA_KM:
        return {
            "ok": False,
            "reason": f"Объект дальше {MAX_EXTRA_KM} км от Брянска — вне зоны обслуживания.",
        }

    cost = round(extra) * PRICE_PER_KM
    return {
        "ok": True, "cost": cost,
        "distance_km": round(distance, 1), "extra_km": round(extra),
        "recognized": geo["result"],
    }