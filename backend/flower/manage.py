"""Local provisioning CLI. No hardware execution capability."""

import argparse
import secrets

from sqlalchemy import select

from flower.auth import hash_secret
from flower.config import Settings
from flower.db import make_engine, sessions
from flower.models import User, Device


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["provision", "rotate", "revoke"])
    parser.add_argument("--device-code", required=True)
    parser.add_argument("--owner-openid")
    parser.add_argument(
        "--source-type", choices=["real", "mock", "demo", "imported_test"], default="mock"
    )
    args = parser.parse_args()
    settings = Settings()
    with sessions(make_engine(settings.database_url)).begin() as db:
        device = db.scalar(
            select(Device).where(Device.device_code == args.device_code).with_for_update()
        )
        if args.action == "provision":
            if device or not args.owner_openid:
                raise SystemExit("Unique device code and owner openid required")
            user = db.scalar(select(User).where(User.openid == args.owner_openid))
            if not user:
                user = User(openid=args.owner_openid)
                db.add(user)
                db.flush()
            device = Device(
                device_code=args.device_code,
                owner_user_id=user.id,
                source_type=args.source_type,
                secret_hash="pending",
            )
            db.add(device)
        elif not device:
            raise SystemExit("Device not found")
        if args.action == "revoke":
            device.revoked = True
            device.token_version += 1
        else:
            secret = secrets.token_urlsafe(48)
            device.secret_hash = hash_secret(secret)
            device.token_version = (device.token_version or 0) + 1
            device.revoked = False
            print("DEVICE_SECRET=" + secret)
    print("Provisioning complete. Store the one-time secret outside Git/logs.")


if __name__ == "__main__":
    main()
