"""
Kiddos - Rate Limiting System (FIXED)
Redis-based sliding window rate limiting with tier-based limits
"""

import time
import asyncio
from typing import Optional, Tuple, Dict, Any
from functools import wraps
from fastapi import HTTPException, Request
import logging

from .database import redis_manager
from .config import RATE_LIMITS, settings
from .models import UserTier

# Configure logging
logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """Rate limit exceeded exception"""

    def __init__(self, limit_type: str, retry_after: int, remaining: int = 0):
        detail = (
            f"Rate limit exceeded for {limit_type}. Try again in {retry_after} seconds."
        )
        super().__init__(
            status_code=429,
            detail=detail,
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Type": limit_type,
            },
        )


class RateLimiter:
    """Redis-based sliding window rate limiter"""

    def __init__(self):
        self.redis = redis_manager
        self.limits = RATE_LIMITS

    async def check_rate_limit(
        self,
        identifier: str,
        limit_type: str,
        tier: str = "free",
        window_seconds: Optional[int] = None,
        max_requests: Optional[int] = None,
    ) -> Tuple[bool, int, int]:
        """
        Check rate limit for identifier

        Returns:
            (allowed: bool, remaining: int, retry_after: int)
        """
        try:
            # Get limit configuration
            if limit_type in self.limits.get(tier, {}):
                max_requests, window_seconds = self.limits[tier][limit_type]
            elif not (window_seconds and max_requests):
                # No limit configured
                return True, 999, 0

            key = f"rate_limit:{tier}:{limit_type}:{identifier}"
            now = time.time()

            # Remove old entries outside window
            await self.redis.zremrangebyscore(key, 0, now - window_seconds)

            # Count current requests in window
            current_count = await self.redis.zcard(key)

            # Check if limit exceeded
            if current_count >= max_requests:
                # Get oldest request to calculate retry_after
                oldest_scores = await self._get_oldest_score(key)
                if oldest_scores:
                    oldest_time = oldest_scores[0][1]
                    retry_after = int(oldest_time + window_seconds - now)
                    retry_after = max(1, retry_after)  # At least 1 second
                else:
                    retry_after = window_seconds

                return False, 0, retry_after

            # Add current request
            await self.redis.zadd(key, {str(now): now})

            # Set expiry to window duration
            await self.redis.expire(key, window_seconds)

            remaining = max_requests - current_count - 1
            return True, remaining, 0

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if Redis is down
            return True, 999, 0

    async def _get_oldest_score(self, key: str):
        """Get oldest score from sorted set"""
        try:
            # Use the Redis client directly for range operations
            result = self.redis.client.zrange(key, 0, 0, withscores=True)
            return result
        except Exception as e:
            logger.error(f"Failed to get oldest score: {e}")
            return []

    async def get_remaining_requests(
        self, identifier: str, limit_type: str, tier: str = "free"
    ) -> int:
        """Get remaining requests for identifier"""
        try:
            if limit_type not in self.limits.get(tier, {}):
                return 999

            max_requests, window_seconds = self.limits[tier][limit_type]
            key = f"rate_limit:{tier}:{limit_type}:{identifier}"
            now = time.time()

            # Clean old entries
            await self.redis.zremrangebyscore(key, 0, now - window_seconds)

            # Count current requests
            current_count = await self.redis.zcard(key)

            return max(0, max_requests - current_count)

        except Exception as e:
            logger.error(f"Failed to get remaining requests: {e}")
            return 999

    async def reset_limits(self, identifier: str, limit_type: str = None):
        """Reset rate limits for identifier"""
        try:
            if limit_type:
                # Reset specific limit type
                pattern = f"rate_limit:*:{limit_type}:{identifier}"
            else:
                # Reset all limits for identifier
                pattern = f"rate_limit:*:*:{identifier}"

            # Use Redis client keys method directly
            keys = list(self.redis.client.scan_iter(match=pattern))
            if keys:
                await self.redis.client.delete(*keys)
                logger.info(
                    f"Reset rate limits for {identifier} ({limit_type or 'all'})"
                )

        except Exception as e:
            logger.error(f"Failed to reset rate limits: {e}")

    async def get_usage_stats(
        self, identifier: str, tier: str = "free"
    ) -> Dict[str, Dict[str, Any]]:
        """Get usage statistics for identifier"""
        try:
            stats = {}

            for limit_type, (max_requests, window_seconds) in self.limits[tier].items():
                key = f"rate_limit:{tier}:{limit_type}:{identifier}"
                now = time.time()

                # Clean old entries
                await self.redis.zremrangebyscore(key, 0, now - window_seconds)

                # Get current usage
                current_count = await self.redis.zcard(key)
                remaining = max(0, max_requests - current_count)

                # Get oldest request for reset time
                oldest_scores = await self._get_oldest_score(key)
                reset_time = None
                if oldest_scores:
                    oldest_time = oldest_scores[0][1]
                    reset_time = oldest_time + window_seconds

                stats[limit_type] = {
                    "limit": max_requests,
                    "used": current_count,
                    "remaining": remaining,
                    "window_seconds": window_seconds,
                    "reset_at": reset_time,
                }

            return stats

        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return {}


# Global rate limiter instance
rate_limiter = RateLimiter()


# Decorator functions
def rate_limit(limit_type: str, tier_override: str = None):
    """
    Rate limiting decorator for FastAPI endpoints

    Usage:
        @rate_limit("content")
        async def generate_content(current_user = Depends(get_current_user)):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from function arguments
            current_user = None
            request = None

            # Look for user in kwargs (dependency injection)
            for value in kwargs.values():
                if hasattr(value, "id") and hasattr(value, "tier"):
                    current_user = value
                    break
                elif hasattr(value, "client"):
                    request = value

            # Look for user in args
            if not current_user:
                for arg in args:
                    if hasattr(arg, "id") and hasattr(arg, "tier"):
                        current_user = arg
                        break
                    elif hasattr(arg, "client"):
                        request = arg

            # Determine identifier and tier
            if current_user:
                identifier = str(current_user.id)
                tier = tier_override or current_user.tier.value
            elif request:
                # Use IP for unauthenticated requests
                identifier = request.client.host
                tier = "free"
            else:
                # No rate limiting if we can't identify
                return await func(*args, **kwargs)

            # Check rate limit
            allowed, remaining, retry_after = await rate_limiter.check_rate_limit(
                identifier=identifier, limit_type=limit_type, tier=tier
            )

            if not allowed:
                raise RateLimitExceeded(limit_type, retry_after, remaining)

            # Add rate limit headers to response (if possible)
            response = await func(*args, **kwargs)

            if hasattr(response, "headers"):
                response.headers["X-RateLimit-Limit"] = str(
                    RATE_LIMITS[tier][limit_type][0]
                )
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Type"] = limit_type

            return response

        return wrapper

    return decorator


def ip_rate_limit(limit_type: str, max_requests: int, window_seconds: int):
    """
    IP-based rate limiting for unauthenticated endpoints

    Usage:
        @ip_rate_limit("registration", 3, 86400)  # 3 per day
        async def register(request: Request):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request object
            request = None
            for value in list(args) + list(kwargs.values()):
                if hasattr(value, "client"):
                    request = value
                    break

            if not request:
                # Can't identify client, allow request
                return await func(*args, **kwargs)

            # Use IP as identifier
            identifier = request.client.host

            # Check rate limit
            allowed, remaining, retry_after = await rate_limiter.check_rate_limit(
                identifier=identifier,
                limit_type=limit_type,
                window_seconds=window_seconds,
                max_requests=max_requests,
            )

            if not allowed:
                raise RateLimitExceeded(limit_type, retry_after, remaining)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts based on system load"""

    def __init__(self):
        self.base_limiter = rate_limiter
        self.load_factor = 1.0
        self.peak_hours = list(range(18, 23))  # 6PM-11PM UAE time

    async def adjust_for_peak_hours(
        self, tier: str, limit_type: str
    ) -> Tuple[int, int]:
        """Adjust limits during peak family hours"""
        import pytz
        from datetime import datetime

        try:
            # Get current hour in UAE timezone
            uae_tz = pytz.timezone("Asia/Dubai")
            current_hour = datetime.now(uae_tz).hour

            base_limit, window = RATE_LIMITS[tier][limit_type]

            # Increase limits during peak family hours
            if current_hour in self.peak_hours:
                if tier in ["basic", "family"]:
                    # 50% more generous during peak hours for paid users
                    adjusted_limit = int(base_limit * 1.5)
                else:
                    # 25% more for free users
                    adjusted_limit = int(base_limit * 1.25)

                return adjusted_limit, window

            return base_limit, window

        except Exception as e:
            logger.error(f"Peak hour adjustment failed: {e}")
            return RATE_LIMITS[tier][limit_type]

    async def get_system_load_factor(self) -> float:
        """Get current system load factor"""
        try:
            # Check Redis latency
            start_time = time.time()
            self.base_limiter.redis.client.ping()
            redis_latency = time.time() - start_time

            # Adjust based on latency
            if redis_latency > 0.1:  # 100ms
                return 0.5  # Reduce limits by 50%
            elif redis_latency > 0.05:  # 50ms
                return 0.8  # Reduce limits by 20%
            else:
                return 1.0  # Normal limits

        except Exception as e:
            logger.error(f"Load factor check failed: {e}")
            return 0.5  # Conservative fallback


# Global adaptive limiter
adaptive_limiter = AdaptiveRateLimiter()


# Background task for cleanup
async def cleanup_expired_rate_limits():
    """Background task to clean up expired rate limit entries"""
    try:
        pattern = "rate_limit:*"
        keys = list(rate_limiter.redis.client.scan_iter(match=pattern))

        cleaned_count = 0
        for key in keys:
            # Remove entries older than 24 hours
            yesterday = time.time() - 86400
            removed = await rate_limiter.redis.zremrangebyscore(key, 0, yesterday)
            cleaned_count += removed

            # Delete empty keys
            if await rate_limiter.redis.zcard(key) == 0:
                await rate_limiter.redis.delete(key)

        logger.info(f"Cleaned up {cleaned_count} expired rate limit entries")

    except Exception as e:
        logger.error(f"Rate limit cleanup failed: {e}")


# Utility functions
async def get_user_rate_limits(user_id: str, tier: str) -> Dict[str, Any]:
    """Get current rate limit status for user"""
    return await rate_limiter.get_usage_stats(user_id, tier)


async def reset_user_rate_limits(user_id: str, limit_type: str = None):
    """Reset rate limits for user (admin function)"""
    await rate_limiter.reset_limits(user_id, limit_type)


# Export main components
__all__ = [
    "rate_limiter",
    "adaptive_limiter",
    "rate_limit",
    "ip_rate_limit",
    "RateLimitExceeded",
    "get_user_rate_limits",
    "reset_user_rate_limits",
    "cleanup_expired_rate_limits",
]
