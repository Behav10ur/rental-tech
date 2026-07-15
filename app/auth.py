import os
from dotenv import load_dotenv
from itsdangerous import URLSafeSerializer, BadSignature
from fastapi import Request

load_dotenv()

COOKIE_NAME = "admin_session"
_serializer = URLSafeSerializer(os.environ["SECRET_KEY"], salt="admin-auth")


def make_session_token() -> str:
    """Подписанный токен для куки."""
    return _serializer.dumps({"role": "admin"})


def is_admin(request: Request) -> bool:
    """Проверяет подпись куки."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        data = _serializer.loads(token)
    except BadSignature:
        return False
    return data.get("role") == "admin"


def check_password(password: str) -> bool:
    return password == os.environ["ADMIN_PASSWORD"]