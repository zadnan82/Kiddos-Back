"""
Kiddos - Main FastAPI Application
Clean architecture with separated routers
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .database import init_database
from .claude_service import claude_service
from .auth import AuthenticationError
from .routers import (
    auth_router,
    user_router,
    children_router,
    content_router,
    credits_router,
    dashboard_router,
    admin_router,
    system_router,
    images_router,
)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(settings.LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting Kiddos application...")

    try:
        # Initialize database
        init_database()
        logger.info("Database initialized successfully")

        # Test Claude API
        health = await claude_service.get_service_health()
        if health.get("status") == "healthy":
            logger.info("Claude API connection verified")
        else:
            logger.warning(f"Claude API health check failed: {health}")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Kiddos application...")


# Create FastAPI application
app = FastAPI(
    title="Kiddos API",
    description="AI-powered educational content platform for children",
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["http://localhost:5173"],
    allow_headers=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)


if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["kiddos.app", "www.kiddos.app", "api.kiddos.app"],
    )


# Global exception handlers
@app.exception_handler(AuthenticationError)
async def auth_exception_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Authentication failed",
            "detail": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the error
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    # Don't expose internal errors in production
    if settings.is_production:
        detail = "An internal error occurred"
    else:
        detail = str(exc)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Log request details
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )

    # Add performance headers
    response.headers["X-Process-Time"] = str(process_time)

    return response


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Welcome to Kiddos API",
        "version": settings.VERSION,
        "docs": "/docs"
        if settings.DEBUG
        else "Documentation available in development mode only",
    }


app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

app.include_router(user_router, prefix="/user", tags=["User Management"])

app.include_router(children_router, prefix="/children", tags=["Child Management"])

app.include_router(content_router, prefix="/content", tags=["Content Generation"])

app.include_router(credits_router, prefix="/credits", tags=["Credit System"])

app.include_router(
    dashboard_router, prefix="/dashboard", tags=["Dashboard & Analytics"]
)

app.include_router(admin_router, prefix="/admin", tags=["Administration"])
app.include_router(images_router, prefix="/images", tags=["images"])
app.include_router(
    system_router,
    prefix="",  # No prefix for health checks
    tags=["System"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
