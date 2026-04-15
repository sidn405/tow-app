from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager
from app.config import settings
from app.database import init_db, close_db, init_redis
from app.api.v1 import auth, drivers, tow_requests, websocket
from app.api.v1 import config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    # add temporarily inside lifespan, after init_db()
    logger.info(f"API prefix: '{settings.API_V1_PREFIX}'")
    logger.info(f"Drivers routes: {[r.path for r in app.routes if 'driver' in str(r.path)]}")
    await init_db()
    await init_redis()
    yield
    logger.info("Shutting down...")
    await close_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan  # use ONLY lifespan, not on_event
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "https://tow-app-production-38dc.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# ── API routes FIRST ──────────────────────────────────────
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

@app.get("/api/v1/config/mapbox-token")
async def get_mapbox_token():
    return {"mapbox_token": settings.MAPBOX_PUBLIC_TOKEN}

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(drivers.router, prefix=settings.API_V1_PREFIX)
app.include_router(tow_requests.router, prefix=settings.API_V1_PREFIX)
app.include_router(websocket.router)
app.include_router(config.router)

# ── Static files LAST — must come after ALL API routes ────
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )