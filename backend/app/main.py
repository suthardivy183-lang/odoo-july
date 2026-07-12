import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (register all tables on Base.metadata)
from app.api import (
    audit_logs,
    audits,
    auth,
    badges,
    carbon,
    categories,
    challenges,
    compliance,
    csr,
    dashboards,
    departments,
    emission_factors,
    erp,
    files,
    gamification,
    goals,
    notifications,
    policies,
    products,
    reports,
    rewards,
    scores,
    trainings,
    users,
)
from app.api import settings as settings_api
from app.core.config import settings
from app.db.session import Base, SessionLocal, engine

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    settings.upload_path  # ensure uploads dir exists
    db = SessionLocal()
    try:
        from app.services.org_settings import get_org_settings

        get_org_settings(db)
        db.commit()
    finally:
        db.close()
    scheduler = None
    if not settings.DISABLE_SCHEDULER:
        from app.core.scheduler import start_scheduler

        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="EcoSphere API",
    version="1.0.0",
    description=(
        "ESG management platform: carbon tracking, CSR, gamification, "
        "governance, scoring and reports. All timestamps UTC; business "
        "timezone Asia/Kolkata; fiscal year April-March."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

ROUTERS = [
    auth.router,
    users.router,
    departments.router,
    categories.router,
    emission_factors.router,
    products.router,
    goals.router,
    erp.router,
    carbon.router,
    csr.router,
    challenges.router,
    gamification.router,
    policies.router,
    trainings.router,
    audits.router,
    compliance.router,
    badges.router,
    rewards.router,
    scores.router,
    reports.router,
    notifications.router,
    settings_api.router,
    audit_logs.router,
    dashboards.router,
    files.router,
]

for r in ROUTERS:
    app.include_router(r, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health", tags=["Health"])
def health():
    return {"status": "ok", "app": "EcoSphere API"}
