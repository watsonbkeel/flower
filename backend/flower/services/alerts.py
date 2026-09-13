from datetime import timedelta
from sqlalchemy import select

from flower.models import Alert, utcnow


def alert(db, device, code, message, *, plant_id=None, hours=6):
    previous = db.scalar(
        select(Alert).where(
            Alert.device_id == device.id,
            Alert.alert_type == code,
            Alert.created_at >= utcnow() - timedelta(hours=hours),
            Alert.resolved_at.is_(None),
        )
    )
    if previous:
        return previous
    item = Alert(
        user_id=device.owner_user_id,
        device_id=device.id,
        plant_id=plant_id,
        alert_type=code,
        title=code,
        message=message,
        suggestion="请检查设备状态与相关配置",
    )
    db.add(item)
    return item
