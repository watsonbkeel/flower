from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from flower.config import Settings
from flower.db import make_engine, ready, sessions


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

    @app.get("/health")
    def health():
        return {"status": "alive", "spec_version": settings.spec_version,
                "software_version": settings.software_version}

    @app.get("/ready")
    def readiness():
        try:
            if ready(engine):
                return {"status": "ready", "spec_version": settings.spec_version}
        except Exception:
            pass
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    return app
