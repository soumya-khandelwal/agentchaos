"""Production Circuit Breaker for autonomous agent tool reliability."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class CircuitState(str, Enum):
    CLOSED = "closed"        # Normal execution; calls allowed
    OPEN = "open"            # Tripped; calls blocked immediately
    HALF_OPEN = "half_open"  # Testing recovery; single probe call allowed


class CircuitBreakerOpenError(RuntimeError):
    """Raised when an agent attempts to invoke a tool whose circuit breaker is tripped."""
    def __init__(self, tool_name: str, retry_after: float):
        super().__init__(
            f"Circuit breaker for tool '{tool_name}' is OPEN. "
            f"Service tripped due to consecutive failures. Retry after {retry_after:.1f}s."
        )
        self.tool_name = tool_name
        self.retry_after = retry_after


class CircuitBreaker(BaseModel):
    """Monitors tool invocations and trips when consecutive failure threshold is exceeded."""
    tool_name: str
    failure_threshold: int = 3
    recovery_timeout: float = 10.0  # seconds before transitioning from OPEN -> HALF_OPEN
    half_open_success_threshold: int = 1

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = Field(default_factory=time.time)

    def can_execute(self) -> bool:
        """Check if execution is currently permitted through this circuit breaker."""
        now = time.time()

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self.last_failure_time and (now - self.last_failure_time) >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.last_state_change = now
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def time_until_retry(self) -> float:
        """Return seconds remaining until circuit breaker enters HALF_OPEN probe state."""
        if self.state != CircuitState.OPEN or not self.last_failure_time:
            return 0.0
        elapsed = time.time() - self.last_failure_time
        remaining = self.recovery_timeout - elapsed
        return max(0.0, remaining)

    def record_success(self) -> None:
        """Record a successful execution."""
        now = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_state_change = now
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self, error: Optional[Any] = None) -> None:
        """Record an execution failure or fault."""
        now = time.time()
        self.last_failure_time = now

        if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.last_state_change = now

    def trip(self) -> None:
        """Manually force the circuit breaker into OPEN state."""
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        self.last_state_change = time.time()

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = time.time()
