"""Одноразовые сообщения через куку (flash)."""
import json
from urllib.parse import quote, unquote
from fastapi import Request, Response

FLASH_COOKIE = "flash"


def set_flash(response: Response, category: str, message: str):
    payload = quote(json.dumps({"category": category, "message": message}))
    response.set_cookie(FLASH_COOKIE, payload, max_age=10, httponly=True, samesite="lax")


def pop_flash(request: Request) -> dict | None:
    raw = request.cookies.get(FLASH_COOKIE)
    if not raw:
        return None
    try:
        return json.loads(unquote(raw))
    except (ValueError, TypeError):
        return None