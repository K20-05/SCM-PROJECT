from contextlib import asynccontextmanager
import logging
import os
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config.app_config import Settings, get_settings
from backend.database.mongo import (
    close_mongo_connection,
    ensure_database_setup,
    get_db,
)
from backend.routes.auth.admin_auth_routes import router as admin_auth_router
from backend.routes.auth.user_auth_routes import router as user_auth_router, user_crud_router
from backend.routes.shipment_routes import router as shipment_router
from backend.routes.user_routes import router as user_router
from core.logger import clear_request_context, configure_logging, set_request_context

configure_logging()
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_database_setup()
    registered_routes = sorted(
        f"{','.join(sorted(route.methods))} {route.path}"
        for route in app.routes
        if hasattr(route, "methods")
    )
    logger.info("Registered routes:\n%s", "\n".join(registered_routes))
    yield
    await close_mongo_connection()


def create_app() -> FastAPI:
    settings = get_settings()
    cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

    app = FastAPI(title="SCMXPertLite API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        set_request_context(request_id=request_id, path=str(request.url.path))
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            logger.info("request completed")
            return response
        finally:
            clear_request_context()

    app.include_router(user_router)
    app.include_router(user_auth_router)
    app.include_router(user_crud_router)
    app.include_router(admin_auth_router)
    app.include_router(shipment_router)

    @app.get("/")
    async def home():
        return {
            "message": "SCMXPertLite API is running",
            "endpoints": {
                "signup": "POST /user/signup",
                "login": "POST /user/login",
                "health": "GET /health",
                "docs": "/docs",
            },
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "scmxpertlite"}

    @app.get("/ping-db")
    async def ping_db(db=Depends(get_db)):
        await db.command("ping")
        return {"db": "connected"}

    @app.get("/info")
    async def info(app_settings: Settings = Depends(get_settings)):
        return {
            "environment": app_settings.environment,
            "version": app_settings.app_version,
            "service": "scmxpertlite",
        }

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run("main:app", host=host, port=port, reload=reload)
