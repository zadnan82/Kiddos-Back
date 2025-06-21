"""
Kiddos - Database Configuration and Session Management (FIXED)
"""

import redis
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from typing import Generator, Optional
import logging
from contextlib import contextmanager

from .config import settings

# Configure logging
logger = logging.getLogger(__name__)

# SQLAlchemy setup
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Validates connections before use
    pool_recycle=3600,  # Recycle connections every hour
    echo=settings.is_development,  # Log SQL in development
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()

# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Base.metadata = MetaData(naming_convention=convention)

# Redis setup
redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=settings.REDIS_MAX_CONNECTIONS,
    decode_responses=True,
)

redis_client = redis.Redis(connection_pool=redis_pool)


class DatabaseManager:
    """Database connection and health management"""

    def __init__(self):
        self.engine = engine
        self.redis_client = redis_client

    async def check_database_health(self) -> bool:
        """Check if database is healthy"""
        try:
            with self.get_db() as db:
                db.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def check_redis_health(self) -> bool:
        """Check if Redis is healthy"""
        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    @contextmanager
    def get_db(self) -> Generator[Session, None, None]:
        """Database session context manager"""
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            db.close()


# Global database manager instance
db_manager = DatabaseManager()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session
    Used with FastAPI Depends()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction failed: {e}")
        raise
    finally:
        db.close()


def get_redis() -> redis.Redis:
    """
    Get Redis client instance
    """
    return redis_client


class RedisManager:
    """Redis operations manager - FIXED"""

    def __init__(self):
        self.client = redis_client

    async def set_with_expiry(self, key: str, value: str, expiry_seconds: int) -> bool:
        """Set key with expiration"""
        try:
            return self.client.setex(key, expiry_seconds, value)
        except Exception as e:
            logger.error(f"Redis set failed for key {key}: {e}")
            return False

    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get failed for key {key}: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """Delete key"""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete failed for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists check failed for key {key}: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter"""
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis increment failed for key {key}: {e}")
            return None

    async def zadd(self, key: str, mapping: dict) -> int:
        """Add to sorted set"""
        try:
            return self.client.zadd(key, mapping)
        except Exception as e:
            logger.error(f"Redis zadd failed for key {key}: {e}")
            return 0

    async def zcard(self, key: str) -> int:
        """Get sorted set cardinality"""
        try:
            return self.client.zcard(key)
        except Exception as e:
            logger.error(f"Redis zcard failed for key {key}: {e}")
            return 0

    async def zremrangebyscore(
        self, key: str, min_score: float, max_score: float
    ) -> int:
        """Remove range from sorted set by score"""
        try:
            return self.client.zremrangebyscore(key, min_score, max_score)
        except Exception as e:
            logger.error(f"Redis zremrangebyscore failed for key {key}: {e}")
            return 0

    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration"""
        try:
            return self.client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis expire failed for key {key}: {e}")
            return False


# Global Redis manager instance
redis_manager = RedisManager()


def init_database():
    """Initialize database tables"""
    try:
        # Import all models to ensure they're registered
        from . import models

        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def cleanup_database():
    """Cleanup database connections"""
    try:
        engine.dispose()
        logger.info("Database connections cleaned up")
    except Exception as e:
        logger.error(f"Database cleanup failed: {e}")


# Health check functions for API endpoints
async def health_check_database() -> dict:
    """Database health check for /health endpoint"""
    try:
        is_healthy = await db_manager.check_database_health()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "details": "Database connection successful"
            if is_healthy
            else "Database connection failed",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "details": f"Database health check error: {str(e)}",
        }


async def health_check_redis() -> dict:
    """Redis health check for /health endpoint"""
    try:
        is_healthy = await db_manager.check_redis_health()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "details": "Redis connection successful"
            if is_healthy
            else "Redis connection failed",
        }
    except Exception as e:
        return {"status": "unhealthy", "details": f"Redis health check error: {str(e)}"}
