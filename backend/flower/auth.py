from datetime import timedelta
import hashlib
import hmac
import secrets

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select

from flower.errors import DomainError
from flower.models import Device, User, utcnow

bearer = HTTPBearer(auto_error=False)


def hash_secret(secret):
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(secret.encode(), salt=salt, n=16384, r=8, p=1).hex()
    return f"scrypt:{salt.hex()}:{value}"


def verify_secret(secret, encoded):
    try:
        algorithm, salt, expected = encoded.split(":")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(secret.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


def issue_token(settings, subject, kind, version=1):
    if len(settings.secret_key) < 32:
        raise DomainError("AUTH_NOT_CONFIGURED", status=503)
    now = utcnow()
    return jwt.encode(
        {
            "sub": subject,
            "kind": kind,
            "ver": version,
            "iss": "flower",
            "aud": "flower-api",
            "iat": now,
            "exp": now + timedelta(minutes=30 if kind == "device" else 120),
        },
        settings.secret_key,
        algorithm="HS256",
    )


def get_db(request: Request):
    with request.app.state.sessions.begin() as db:
        yield db


def principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(get_db),
):
    if credentials is None:
        raise DomainError("AUTH_REQUIRED", status=401)
    try:
        payload = jwt.decode(
            credentials.credentials,
            request.app.state.settings.secret_key,
            algorithms=["HS256"],
            issuer="flower",
            audience="flower-api",
            options={"require": ["exp", "iat", "sub", "kind", "ver"]},
        )
        kind = payload["kind"]
        if kind not in {"user", "device"}:
            raise ValueError()
        entity = db.get(User if kind == "user" else Device, payload["sub"])
        if entity is None or (
            kind == "device" and (entity.revoked or entity.token_version != payload["ver"])
        ):
            raise ValueError()
        return kind, entity
    except (jwt.PyJWTError, ValueError, TypeError):
        raise DomainError("INVALID_TOKEN", status=401) from None


def require_user(identity=Depends(principal)):
    if identity[0] != "user":
        raise DomainError("USER_TOKEN_REQUIRED", status=403)
    return identity[1]


def require_device(identity=Depends(principal)):
    if identity[0] != "device":
        raise DomainError("DEVICE_TOKEN_REQUIRED", status=403)
    return identity[1]


def owned_plant(db, plant_id, user_id):
    from flower.models import Plant

    plant = db.scalar(select(Plant).where(Plant.id == plant_id, Plant.user_id == user_id))
    if plant is None:
        raise DomainError("NOT_FOUND", status=404)
    return plant
