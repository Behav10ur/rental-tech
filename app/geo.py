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


def geocode(address: str) -> tuple[float, float] | None:
    """Адрес → (широта, долгота). None, если не удалось определить."""
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
    if lat is None or lon is None:
        return None

    return float(lat), float(lon)


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
    Возвращает dict со статусом:
      - ok=True, cost, distance_km, extra_km  — обслуживаем
      - ok=False, reason                       — не обслуживаем / не распознан адрес
    """
    coords = geocode(address)
    if coords is None:
        return {"ok": False, "reason": "Не удалось определить адрес. Уточните его."}

    lat, lon = coords
    distance = haversine_km(ORIGIN_LAT, ORIGIN_LON, lat, lon)

    # внутри объездной — бесплатно
    if distance <= BELTWAY_RADIUS_KM:
        return {"ok": True, "cost": 0, "distance_km": round(distance, 1), "extra_km": 0}

    extra = distance - BELTWAY_RADIUS_KM  # км сверх объездной

    if extra > MAX_EXTRA_KM:
        return {
            "ok": False,
            "reason": f"Объект дальше {MAX_EXTRA_KM} км от Брянска — вне зоны обслуживания.",
        }

    cost = round(extra) * PRICE_PER_KM
    return {
        "ok": True,
        "cost": cost,
        "distance_km": round(distance, 1),
        "extra_km": round(extra),
    }