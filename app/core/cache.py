"""
Cache and Rate Limiting Module
"""
from typing import Optional, Any
import json
import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Redis cache manager."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis_client.ping()
            logger.info("redis_connected")
        except Exception as e:
            logger.error("redis_connection_error", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("redis_disconnected")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("cache_get_error", key=key, error=str(e))
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        try:
            ttl = ttl or settings.REDIS_CACHE_TTL
            serialized = json.dumps(value)
            await self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error("cache_set_error", key=key, error=str(e))
            return False


class RateLimiter:
    """Rate limiter using Redis."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
    
    async def is_allowed(self, identifier: str, max_requests: Optional[int] = None,
                        window: Optional[int] = None) -> bool:
        """Check if request is allowed."""
        try:
            max_requests = max_requests or settings.RATE_LIMIT_REQUESTS
            window = window or settings.RATE_LIMIT_PERIOD
            
            key = f"rate_limit:{identifier}"
            current = await self.cache.redis_client.get(key)
            
            if current is None:
                await self.cache.redis_client.setex(key, window, 1)
                return True
            
            current_count = int(current)
            
            if current_count >= max_requests:
                logger.warning("rate_limit_exceeded", identifier=identifier)
                return False
            
            await self.cache.redis_client.incr(key)
            return True
        except Exception as e:
            logger.error("rate_limit_error", error=str(e))
            return True  # Fail open


cache_manager = CacheManager()
rate_limiter = RateLimiter(cache_manager)