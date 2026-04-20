"""Response caching for LLM agents."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from django.core.cache import cache

from djgent.runtime.middleware import ExecutionContext

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Represents a cached response."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    hits: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if the cache entry is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hits": self.hits,
            "metadata": self.metadata,
        }


class ResponseCache:
    """
    Caching layer for LLM responses.
    
    Supports:
    - In-memory caching
    - Django cache backend
    - TTL (time to live) expiration
    - Cache invalidation
    - Statistics tracking
    
    Example:
        # Initialize cache
        cache = ResponseCache(
            backend="django",
            ttl_seconds=300,
            max_entries=1000
        )
        
        # Cache a response
        cache.set("prompt_hash", "LLM response here")
        
        # Get cached response
        cached = cache.get("prompt_hash")
        
        # Or use as decorator
        @cache.cached(ttl_seconds=60)
        async def get_llm_response(prompt: str) -> str:
            ...
    """

    def __init__(
        self,
        backend: str = "memory",
        ttl_seconds: int = 300,
        max_entries: int = 1000,
        key_prefix: str = "djgent_cache",
    ):
        """
        Initialize the response cache.
        
        Args:
            backend: Cache backend ("memory", "django", or "both")
            ttl_seconds: Default time to live in seconds
            max_entries: Maximum number of cache entries
            key_prefix: Prefix for cache keys
        """
        self.backend = backend
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.key_prefix = key_prefix
        self._memory_store: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }

    def _make_key(self, key: str) -> str:
        """Create a full cache key with prefix."""
        return f"{self.key_prefix}:{key}"

    def _hash_key(self, data: Any) -> str:
        """Hash data to create a cache key."""
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        else:
            data_bytes = json.dumps(data, sort_keys=True).encode('utf-8')
        return hashlib.sha256(data_bytes).hexdigest()[:32]

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)
            metadata: Additional metadata
        """
        ttl = ttl or self.ttl_seconds
        expires_at = time.time() + ttl if ttl > 0 else None

        entry = CacheEntry(
            key=key,
            value=value,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        with self._lock:
            # Evict if at capacity
            if len(self._memory_store) >= self.max_entries and key not in self._memory_store:
                self._evict_oldest()

            self._memory_store[key] = entry
            self._stats["sets"] += 1

        # Also set in Django cache if configured
        if self.backend in ("django", "both"):
            try:
                cache.set(self._make_key(key), entry.to_dict(), ttl)
            except Exception:
                pass  # Silently ignore cache errors

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        entry: Optional[CacheEntry] = None

        # Try memory store first
        with self._lock:
            if key in self._memory_store:
                entry = self._memory_store[key]

        # Try Django cache if not in memory
        if entry is None and self.backend in ("django", "both"):
            try:
                data = cache.get(self._make_key(key))
                if data:
                    entry = CacheEntry(**data)
            except Exception:
                pass

        if entry is None:
            self._stats["misses"] += 1
            return None

        if entry.is_expired():
            self.delete(key)
            self._stats["misses"] += 1
            return None

        # Update hit count
        with self._lock:
            if key in self._memory_store:
                self._memory_store[key].hits += 1

        self._stats["hits"] += 1
        return entry.value

    def delete(self, key: str) -> None:
        """
        Delete a key from the cache.
        
        Args:
            key: Cache key to delete
        """
        with self._lock:
            self._memory_store.pop(key, None)

        if self.backend in ("django", "both"):
            try:
                cache.delete(self._make_key(key))
            except Exception:
                pass

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._memory_store.clear()

        if self.backend in ("django", "both"):
            try:
                # Use cache.iter_keys() if available (Redis), otherwise use get_many approach
                # For Django cache, we'll track keys ourselves instead of using KEYS
                if hasattr(cache, 'iter_keys'):
                    # Redis-compatible iteration
                    for key in cache.iter_keys(f"{self.key_prefix}:*"):
                        cache.delete(key)
                else:
                    # For other backends, we can't easily iterate
                    # This is a limitation - consider using a key tracking set
                    pass
            except Exception:
                pass

    def _evict_oldest(self) -> None:
        """Evict the oldest entry from memory cache."""
        if not self._memory_store:
            return

        oldest_key = min(
            self._memory_store.keys(),
            key=lambda k: self._memory_store[k].created_at
        )
        del self._memory_store[oldest_key]
        self._stats["evictions"] += 1

    def cached(
        self,
        ttl: Optional[int] = None,
        key_func: Optional[Callable[..., str]] = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """
        Decorator to cache function results.
        
        Args:
            ttl: Time to live in seconds
            key_func: Function to generate cache key from args
            
        Returns:
            Decorated function
            
        Example:
            @cache.cached(ttl=60)
            def get_weather(location: str) -> dict:
                ...
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            def wrapper(*args: Any, **kwargs: Any) -> T:
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    key_data = {"func": func.__name__, "args": args, "kwargs": kwargs}
                    cache_key = self._hash_key(key_data)

                # Try to get from cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # Execute function and cache result
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl=ttl)
                return result

            return wrapper  # type: ignore
        return decorator

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (
                self._stats["hits"] / total_requests
                if total_requests > 0
                else 0.0
            )

            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "sets": self._stats["sets"],
                "evictions": self._stats["evictions"],
                "hit_rate": hit_rate,
                "total_requests": total_requests,
                "entries": len(self._memory_store),
                "max_entries": self.max_entries,
            }

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        with self._lock:
            self._stats = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "evictions": 0,
            }


# Global cache instance
response_cache = ResponseCache()


# Cache middleware for agents
class CacheMiddleware:
    """
    Middleware for caching agent responses.
    
    Example:
        cache_middleware = CacheMiddleware(ttl_seconds=300)
        
        agent = Agent(
            name="my_agent",
            middleware=[cache_middleware]
        )
    """

    def __init__(
        self,
        cache: Optional[ResponseCache] = None,
        ttl_seconds: int = 300,
        enabled: bool = True,
    ):
        """
        Initialize cache middleware.
        
        Args:
            cache: ResponseCache instance
            ttl_seconds: Default TTL for cached responses
            enabled: Whether caching is enabled
        """
        self.cache = cache or response_cache
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

    def get_cache_key(
        self,
        agent_name: str,
        message: str,
        thread_id: Optional[str] = None,
    ) -> str:
        """Generate a cache key for an agent run."""
        key_data = {
            "agent_name": agent_name,
            "message": message,
            "thread_id": thread_id,
        }
        return self.cache._hash_key(key_data)

    def get_cached_response(
        self,
        agent_name: str,
        message: str,
        thread_id: Optional[str] = None,
    ) -> Optional[str]:
        """Get cached response for an agent run."""
        if not self.enabled:
            return None

        key = self.get_cache_key(agent_name, message, thread_id)
        return self.cache.get(key)

    def cache_response(
        self,
        agent_name: str,
        message: str,
        response: str,
        thread_id: Optional[str] = None,
    ) -> None:
        """Cache an agent response."""
        if not self.enabled:
            return

        key = self.get_cache_key(agent_name, message, thread_id)
        self.cache.set(
            key,
            response,
            ttl=self.ttl_seconds,
            metadata={
                "agent_name": agent_name,
                "thread_id": thread_id,
            }
        )

    def before_run(self, execution: ExecutionContext) -> None:
        """
        Check cache before agent run.
        
        If cached response exists, store it in execution metadata for after_run to return.
        """
        if not self.enabled:
            return

        cached = self.get_cached_response(
            agent_name=execution.agent_name,
            message=execution.input,
            thread_id=execution.thread_id,
        )
        
        if cached is not None:
            execution.metadata["cached_response"] = cached
            execution.metadata["cache_hit"] = True

    def after_run(self, execution: ExecutionContext, output: str) -> str:
        """
        Cache the response after agent run if not already cached.
        """
        if not self.enabled:
            return output

        # If we already had a cached response, just return it
        if execution.metadata.get("cache_hit"):
            return execution.metadata.get("cached_response", output)

        # Cache the new response
        self.cache_response(
            agent_name=execution.agent_name,
            message=execution.input,
            response=output,
            thread_id=execution.thread_id,
        )
        
        return output

    def invalidate(
        self,
        agent_name: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> None:
        """Invalidate cached responses."""
        if agent_name and thread_id:
            # Invalidate specific thread
            key_data = {
                "agent_name": agent_name,
                "message": "",  # Would need to track all messages
                "thread_id": thread_id,
            }
            key = self.cache._hash_key(key_data)
            self.cache.delete(key)
        else:
            self.cache.clear()
