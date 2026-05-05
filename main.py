from contextlib import asynccontextmanager
import logging

import uvicorn
from fastapi import FastAPI

from backend.database.mongo import ensure_indexes
from backend.routes.user_routes import router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    registered_routes = sorted(
        f"{','.join(sorted(route.methods))} {route.path}"
        for route in app.routes
        if hasattr(route, "methods")
    )
    logger.info("Registered routes:\n%s", "\n".join(registered_routes))
    yield


app = FastAPI(title="Signup and Login API", lifespan=lifespan)
app.include_router(router)


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


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
