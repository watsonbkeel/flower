from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

from flower.config import Settings
from flower.db import make_engine, ready, sessions
from flower.errors import DomainError


def create_app(settings=None):
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="Flower", version=settings.spec_version, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessions = sessions(engine)

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(
            status_code=exc.status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "detail": {},
                    "retryable": exc.retryable,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "请求字段不合法",
                    "detail": {"fields": [list(e["loc"]) for e in exc.errors()]},
                    "retryable": False,
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def constraint_error(request, exc):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CONSTRAINT_CONFLICT",
                    "message": "资源状态冲突，请刷新后重试",
                    "detail": {},
                    "retryable": False,
                }
            },
        )

    from flower.api.device import router as device_router
    from flower.api.plants import router as plants_router
    from flower.api.media import router as media_router

    app.include_router(device_router)
    app.include_router(plants_router)
    app.include_router(media_router)

    @app.get("/health")
    def health():
        return {
            "status": "alive",
            "spec_version": settings.spec_version,
            "software_version": settings.software_version,
        }

    @app.get("/ready")
    def readiness():
        try:
            if ready(engine):
                return {"status": "ready", "spec_version": settings.spec_version}
        except Exception:
            pass
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    return app
