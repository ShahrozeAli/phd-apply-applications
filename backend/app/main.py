from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.discovery import run_discovery
from app.services.profile_service import get_or_create_profile

scheduler = BackgroundScheduler()


def _daily_job():
    db = SessionLocal()
    try:
        run_discovery(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        get_or_create_profile(db)
    finally:
        db.close()
    scheduler.add_job(
        _daily_job,
        "cron",
        hour=settings.daily_discovery_hour,
        minute=settings.daily_discovery_minute,
        id="daily_discovery",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="PhD Apply Bot",
    description="Discovery and tracking assistant for fully funded European PhD positions.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
