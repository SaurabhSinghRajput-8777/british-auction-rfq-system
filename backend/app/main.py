import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.seeds import seed_demo_data
from app.api.routes import router
from app.services.scheduler import check_and_close_expired_auctions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema verified/created.")

    # Seed demo users & carriers
    db = SessionLocal()
    try:
        seed_demo_data(db)
        logger.info("Demo seeds verified.")
    finally:
        db.close()

    # Start background scheduler if enabled
    if settings.SCHEDULER_ENABLED:
        scheduler.add_job(
            check_and_close_expired_auctions,
            "interval",
            seconds=settings.SCHEDULER_INTERVAL_SECONDS,
            id="rfq_closure_job",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(f"Auction closure scheduler started (interval: {settings.SCHEDULER_INTERVAL_SECONDS}s).")

    yield

    if settings.SCHEDULER_ENABLED and scheduler.running:
        scheduler.shutdown()
        logger.info("Auction closure scheduler stopped.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Standard error envelope mapping
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_SERVER_ERROR", "detail": str(exc)},
    )


# Health check endpoint
@app.get("/api/v1/health")
def health_check():
    from app.services.auction_service import get_db_clock
    db = SessionLocal()
    try:
        clock = get_db_clock(db)
        return {
            "status": "ok",
            "server_time": clock.isoformat(),
            "scheduler_running": scheduler.running if settings.SCHEDULER_ENABLED else False,
        }
    finally:
        db.close()


# Mount main API router
app.include_router(router, prefix=settings.API_V1_PREFIX)
