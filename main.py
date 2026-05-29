from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.config.app_config import Settings, get_settings
from backend.database.mongo import (
    close_mongo_connection,
    ensure_database_setup,
    get_db,
)
from backend.routes.auth.admin_auth_routes import router as admin_auth_router
from backend.routes.auth.user_auth_routes import router as user_auth_router, user_crud_router
from backend.routes.device_routes import router as device_router
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
    project_root = Path(__file__).resolve().parent
    frontend_dir = project_root / "frontend"

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

    # Legacy /user routes remain active for backward compatibility but are hidden
    # from Swagger; prefer /api/auth endpoints.
    app.include_router(user_router, include_in_schema=False)
    app.include_router(user_auth_router)
    app.include_router(user_crud_router)
    app.include_router(admin_auth_router)
    app.include_router(device_router)
    app.include_router(shipment_router)

    app.mount("/css", StaticFiles(directory=frontend_dir / "css"), name="css")
    app.mount("/javascript", StaticFiles(directory=frontend_dir / "javascript"), name="javascript")

    @app.get("/")
    async def home():
        return RedirectResponse(url="/signup", status_code=307)

    @app.get("/signup")
    async def signup_page():
        return FileResponse(frontend_dir / "html_files" / "signup.html")

    @app.get("/login")
    async def login_page():
        return FileResponse(frontend_dir / "html_files" / "login.html")

    @app.get("/dashboard")
    async def dashboard_page():
        return FileResponse(frontend_dir / "html_files" / "dashboard.html")

    @app.get("/signup-dark")
    async def signup_dark_page():
        return RedirectResponse(url="/signup?theme=dark", status_code=307)

    # Backward-compatible route name.
    @app.get("/signup-dark")
    async def signup_industrial_page():
        return RedirectResponse(url="/signup-dark", status_code=307)

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
