"""Rate limiting middleware for Djgent agents."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from djgent.runtime.middleware import AgentMiddleware, ExecutionContext


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10
    enabled: bool = True


@dataclass
class RateLimitState:
    """Tracks rate limit state for a key."""

    request_times: list[float] = field(default_factory=list)
    hourly_times: list[float] = field(default_factory=list)
    daily_times: list[float] = field(default_factory=list)
    burst_count: int = 0
    last_reset: float = field(default_factory=time.time)


class RateLimitMiddleware(AgentMiddleware):
    """
    Rate limiting middleware to prevent abuse.

    Tracks requests per minute, hour, and day for each unique key
    (e.g., user_id, agent_name, or IP address).

    State is automatically evicted for keys that have been idle for
    longer than the daily window to prevent unbounded memory growth.

    Example:
        # Global rate limiter
        limiter = RateLimitMiddleware(
            requests_per_minute=30,
            requests_per_hour=500
        )

        # Add to agent
        agent = Agent(
            name="my_agent",
            middleware=[limiter]
        )

        # Or use as a decorator
        @limiter.limit("user_123")
        async def my_function():
            ...
    """

    # Time-to-live for idle keys (24 hours matches the daily window)
    _KEY_TTL_SECONDS: float = 86400

    def __init__(
        self,
        *,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000,
        burst_size: int = 10,
        key_func: Optional[Callable[[ExecutionContext], str]] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
            requests_per_hour: Maximum requests allowed per hour
            requests_per_day: Maximum requests allowed per day
            burst_size: Maximum burst requests allowed
            key_func: Optional function to extract rate limit key from ExecutionContext
        """
        self.config = RateLimitConfig(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            requests_per_day=requests_per_day,
            burst_size=burst_size,
        )
        self._state: Dict[str, RateLimitState] = {}
        self._lock = threading.RLock()
        self._key_func = key_func or self._default_key_func

    def _default_key_func(self, execution: ExecutionContext) -> str:
        """Default key function uses agent_name and thread_id."""
        return f"{execution.agent_name}:{execution.thread_id}"

    def _get_state(self, key: str) -> RateLimitState:
        """Get or create rate limit state for a key."""
        with self._lock:
            self._evict_idle_keys()
            if key not in self._state:
                self._state[key] = RateLimitState()
            return self._state[key]

    def _evict_idle_keys(self) -> None:
        """Remove keys that have been idle longer than the TTL."""
        now = time.time()
        idle_keys = [
            k
            for k, state in self._state.items()
            if state.daily_times and (now - state.daily_times[-1]) > self._KEY_TTL_SECONDS
        ]
        for key in idle_keys:
            del self._state[key]

    def _cleanup_old_requests(self, state: RateLimitState) -> None:
        """Remove requests older than the time windows."""
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        day_ago = now - 86400

        state.request_times = [t for t in state.request_times if t > minute_ago]
        state.hourly_times = [t for t in state.hourly_times if t > hour_ago]
        state.daily_times = [t for t in state.daily_times if t > day_ago]

    def _check_rate_limit(self, key: str) -> tuple[bool, str]:
        """
        Check if request is within rate limits.

        Returns:
            Tuple of (is_allowed, reason)
        """
        state = self._get_state(key)
        now = time.time()

        self._cleanup_old_requests(state)

        # Check daily limit
        if len(state.daily_times) >= self.config.requests_per_day:
            return False, "Daily rate limit exceeded"

        # Check hourly limit
        if len(state.hourly_times) >= self.config.requests_per_hour:
            return False, "Hourly rate limit exceeded"

        # Check minute limit
        if len(state.request_times) >= self.config.requests_per_minute:
            return False, "Minute rate limit exceeded"

        # Check burst limit
        if state.burst_count >= self.config.burst_size:
            # Check if we can allow burst
            if state.request_times:
                time_since_last = now - state.request_times[-1]
                if time_since_last < 1.0:  # Less than 1 second since last request
                    return False, "Burst limit exceeded"

        return True, ""

    def _record_request(self, key: str) -> None:
        """Record a request for rate limiting."""
        state = self._get_state(key)
        now = time.time()

        state.request_times.append(now)
        state.hourly_times.append(now)
        state.daily_times.append(now)
        state.burst_count += 1

    def before_run(self, execution: ExecutionContext) -> None:
        """
        Check rate limits before agent run.

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        if not self.config.enabled:
            return

        key = self._key_func(execution)
        allowed, reason = self._check_rate_limit(key)

        if not allowed:
            from djgent.exceptions import RateLimitError

            raise RateLimitError(
                message=f"Rate limit exceeded: {reason}",
                limit_type=reason,
            )

        self._record_request(key)
        execution.metadata["rate_limit_key"] = key
        execution.metadata["rate_limit_allowed"] = True

    def after_run(self, execution: ExecutionContext, output: str) -> str:
        """Record successful completion."""
        # Could add additional tracking here if needed
        return output

    def get_remaining_requests(self, key: str) -> Dict[str, int]:
        """Get remaining requests for a key."""
        state = self._get_state(key)
        self._cleanup_old_requests(state)

        return {
            "minute": max(0, self.config.requests_per_minute - len(state.request_times)),
            "hour": max(0, self.config.requests_per_hour - len(state.hourly_times)),
            "day": max(0, self.config.requests_per_day - len(state.daily_times)),
            "burst": max(0, self.config.burst_size - state.burst_count),
        }

    def reset_limits(self, key: Optional[str] = None) -> None:
        """
        Reset rate limits for a key or all keys.

        Args:
            key: Specific key to reset, or None to reset all
        """
        with self._lock:
            if key:
                self._state.pop(key, None)
            else:
                self._state.clear()

    def is_rate_limited(self, key: str) -> bool:
        """Check if a key is currently rate limited."""
        allowed, _ = self._check_rate_limit(key)
        return not allowed
