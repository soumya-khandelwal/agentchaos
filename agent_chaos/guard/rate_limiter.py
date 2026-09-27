"""Sliding-window rate limiter for preventing agent runaway loops and API exhaustion."""

from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, Optional


class RateLimitExceededError(RuntimeError):
    """Raised when an agent exceeds the maximum allowed calls per time window."""
    def __init__(self, tool_name: str, max_calls: int, window_seconds: float):
        super().__init__(
            f"Rate limit exceeded for tool '{tool_name}': "
            f"maximum {max_calls} calls per {window_seconds:.1f}s allowed."
        )
        self.tool_name = tool_name
        self.max_calls = max_calls
        self.window_seconds = window_seconds


class SlidingWindowRateLimiter:
    """Sliding-window in-memory rate limiter per tool."""

    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._history: Deque[float] = deque()

    def check_and_record(self) -> bool:
        """Check if a call is allowed and record the timestamp. Returns False if limit exceeded."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Evict timestamps older than the sliding window
        while self._history and self._history[0] <= cutoff:
            self._history.popleft()

        if len(self._history) >= self.max_calls:
            return False

        self._history.append(now)
        return True

    def current_usage(self) -> int:
        """Return the number of calls within the active sliding window."""
        now = time.time()
        cutoff = now - self.window_seconds
        while self._history and self._history[0] <= cutoff:
            self._history.popleft()
        return len(self._history)

    def reset(self) -> None:
        """Clear all recorded timestamps."""
        self._history.clear()
