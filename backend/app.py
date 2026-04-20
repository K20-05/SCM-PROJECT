from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from backend.db.database import users_collection
from backend.routes.user import router as user_router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await users_collection.create_index("email", unique=True)
    registered_routes = sorted(
        f"{','.join(sorted(route.methods))} {route.path}"
        for route in app.routes
        if hasattr(route, "methods")
    )
    logger.info("Registered routes:\n%s", "\n".join(registered_routes))
    yield


app = FastAPI(title="Signup and Login API", lifespan=lifespan)
app.include_router(user_router)


@app.get("/")
async def home():
    return {
        "message": "Signup and Login API is running",
        "endpoints": {
            "signup": "POST /user/signup",
            "login": "POST /user/login",
            "health": "GET /health",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
