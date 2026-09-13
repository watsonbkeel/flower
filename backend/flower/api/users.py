from uuid import UUID

from fastapi import APIRouter, Depends, Request
import httpx
from pydantic import Field
from sqlalchemy import select

from flower.auth import get_db, require_user, issue_token, owned_plant
from flower.errors import DomainError
from flower.models import User, Alert, Event
from flower.schemas import StrictModel, serialize

router = APIRouter(prefix="/api/v1")


class WechatLogin(StrictModel):
    code: str = Field(min_length=1, max_length=300)


@router.post("/auth/wechat-login")
def login(data: WechatLogin, request: Request, db=Depends(get_db)):
    settings = request.app.state.settings
    request.app.state.rate_limiter.check("login:" + request.client.host, limit=10)
    mock = (
        settings.app_env != "production"
        and settings.provider_mode == "mock"
        and data.code.startswith("mock-")
    )
    if mock:
        openid = data.code
    else:
        if not settings.wechat_app_id or not settings.wechat_app_secret:
            raise DomainError("WECHAT_NOT_CONFIGURED", status=503)
        try:
            response = httpx.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                timeout=10,
                params={
                    "appid": settings.wechat_app_id,
                    "secret": settings.wechat_app_secret,
                    "js_code": data.code,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errcode") or not payload.get("openid"):
                raise ValueError()
            openid = payload["openid"]
        except (httpx.HTTPError, ValueError):
            raise DomainError("WECHAT_LOGIN_FAILED", status=401) from None
    user = db.scalar(select(User).where(User.openid == openid))
    if not user:
        user = User(openid=openid)
        db.add(user)
        db.flush()
    return {
        "access_token": issue_token(settings, user.id, "user"),
        "user_id": user.id,
        "source_type": "mock" if mock else "real",
        "spec_version": "2.2.2",
    }


@router.get("/plants/{plant_id}/events")
def events(plant_id: UUID, user=Depends(require_user), db=Depends(get_db)):
    plant = owned_plant(db, str(plant_id), user.id)
    return [
        serialize(event)
        for event in db.scalars(
            select(Event)
            .where(Event.plant_id == plant.id)
            .order_by(Event.occurred_at.desc())
            .limit(200)
        )
    ]


@router.get("/alerts")
def alerts(user=Depends(require_user), db=Depends(get_db)):
    return [
        serialize(item)
        for item in db.scalars(
            select(Alert)
            .where(Alert.user_id == user.id)
            .order_by(Alert.created_at.desc())
            .limit(200)
        )
    ]


@router.put("/alerts/{alert_id}/read")
def read_alert(alert_id: UUID, user=Depends(require_user), db=Depends(get_db)):
    alert = db.scalar(select(Alert).where(Alert.id == str(alert_id), Alert.user_id == user.id))
    if not alert:
        raise DomainError("NOT_FOUND", status=404)
    alert.is_read = True
    return serialize(alert)
