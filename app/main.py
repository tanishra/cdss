"""
Main FastAPI Application
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from datetime import datetime
from sqlalchemy import text
import time

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db, close_db
from app.core.cache import cache_manager
from app.api.auth import router as auth_router
from app.api.routes import patient_router, diagnosis_router
from app.api.feedback import router as feedback_router
from app.api.treatments import router as treatment_router
from app.api import treatments, clinical
from app.schemas.schemas import HealthCheck
from app.utils.correlation import get_correlation_id

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("application_startup", version=settings.APP_VERSION)
    
    try:
        await init_db()
        await cache_manager.connect()
        logger.info("services_initialized")
    except Exception as e:
        logger.error("startup_error", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("application_shutdown")
    try:
        await cache_manager.disconnect()
        await close_db()
    except Exception as e:
        logger.error("shutdown_error", error=str(e))


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with correlation ID and timing."""
    correlation_id = get_correlation_id(request)
    start_time = time.time()
    
    logger.info(
        "request_started",
        method=request.method,
        path=request.url.path,
        correlation_id=correlation_id,
    )
    
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
        )
        
        return response
    except Exception as e:
        logger.error("request_failed", error=str(e), correlation_id=correlation_id)
        raise


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    correlation_id = get_correlation_id(request)
    
    logger.warning("validation_error", errors=exc.errors(), correlation_id=correlation_id)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": str(exc.errors()),
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    correlation_id = get_correlation_id(request)
    
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        correlation_id=correlation_id,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# Include routers
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(patient_router, prefix=settings.API_PREFIX)
app.include_router(diagnosis_router, prefix=settings.API_PREFIX)
app.include_router(feedback_router, prefix=settings.API_PREFIX)
# app.include_router(treatment_router,prefix=settings.API_PREFIX)
app.include_router(
    treatments.router,
    prefix="/api/v1/treatments",
    tags=["treatments"],
)
app.include_router(
    clinical.router,
    prefix="/api/v1/clinical",
    tags=["clinical"],
)

@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Check application health status."""
    db_status = "healthy"
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    redis_status = "healthy"
    try:
        await cache_manager.redis_client.ping()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    overall_status = "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded"
    
    return HealthCheck(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=settings.APP_VERSION,
        database=db_status,
        redis=redis_status,
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }