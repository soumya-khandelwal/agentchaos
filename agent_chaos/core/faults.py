"""Fault specifications and definitions for AgentChaos."""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union
from pydantic import BaseModel, Field


class FaultType(str, Enum):
    """Types of faults that can be injected into agent tools."""
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    RATE_LIMIT = "rate_limit"
    MALFORMED_DATA = "malformed_data"
    LATENCY = "latency"
    CUSTOM_EXCEPTION = "custom_exception"
    POISONED_PAYLOAD = "poisoned_payload"
    EMPTY_GROUNDING = "empty_grounding"
    STALE_GROUNDING = "stale_grounding"


class FaultTrigger(str, Enum):
    """When the fault should be triggered during execution."""
    ALWAYS = "always"
    N_TIMES = "n_times"
    AFTER_N_CALLS = "after_n_calls"


class Fault(BaseModel):
    """Defines a chaos fault to be injected into an agent tool call."""

    fault_type: FaultType
    trigger: FaultTrigger = FaultTrigger.ALWAYS
    times: Optional[int] = None
    delay: float = 0.0
    status_code: int = 500
    message: str = "Internal Server Error"
    payload: Optional[Any] = None
    custom_exception: Optional[Exception] = None
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None

    class Config:
        arbitrary_types_allowed = True

    # Factory methods for clean DX
    @classmethod
    def timeout(cls, delay: float = 0.0, times: Optional[int] = None, message: Optional[str] = None) -> "Fault":
        """Simulate a network or execution timeout."""
        return cls(
            fault_type=FaultType.TIMEOUT,
            trigger=FaultTrigger.N_TIMES if times is not None else FaultTrigger.ALWAYS,
            times=times,
            delay=delay,
            message=message or f"Tool execution timed out after {delay}s",
        )

    @classmethod
    def http_error(
        cls,
        status_code: int = 500,
        message: str = "Internal Server Error",
        times: Optional[int] = None,
        payload: Optional[Any] = None,
    ) -> "Fault":
        """Simulate an HTTP error (500, 502, 503, 504, etc.)."""
        return cls(
            fault_type=FaultType.HTTP_ERROR,
            trigger=FaultTrigger.N_TIMES if times is not None else FaultTrigger.ALWAYS,
            times=times,
            status_code=status_code,
            message=message,
            payload=payload or {"error": message, "code": status_code},
        )

    @classmethod
    def rate_limit(cls, times: Optional[int] = None, retry_after: int = 60) -> "Fault":
        """Simulate an HTTP 429 Too Many Requests error."""
        return cls(
            fault_type=FaultType.RATE_LIMIT,
            trigger=FaultTrigger.N_TIMES if times is not None else FaultTrigger.ALWAYS,
            times=times,
            status_code=429,
            message=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            payload={"error": "Too Many Requests", "retry_after": retry_after},
        )

    @classmethod
    def malformed(cls, payload: Optional[Any] = None, times: Optional[int] = None) -> "Fault":
        """Simulate a broken, truncated, or invalid schema response."""
        return cls(
            fault_type=FaultType.MALFORMED_DATA,
            trigger=FaultTrigger.N_TIMES if times is not None else FaultTrigger.ALWAYS,
            times=times,
            payload=payload if payload is not None else {"corrupted": True, "_incomplete": [None]},
            message="Malformed or unexpected tool response data",
        )

    @classmethod
    def latency(cls, seconds: float = 2.0, times: Optional[int] = None) -> "Fault":
        """Simulate slow downstream API or network latency before succeeding."""
        return cls(
            fault_type=FaultType.LATENCY,
            trigger=FaultTrigger.N_TIMES if times is not None else FaultTrigger.ALWAYS,
            times=times,
            delay=seconds,
        )

    @classmethod
    def poisoned(cls, payload: str, times: Optional[int] = None) -> "Fault":
        """Simulate an adversarial payload or indirect prompt injection in tool output."""
        return cls(
            fault_type=FaultType.POISONED_PAYLOAD,
            trigger=FaultTrigger.N_TIMES if times is not None else FaultTrigger.ALWAYS,
            times=times,
            payload=payload,
            message="Adversarial poisoned payload injected",
        )

    @classmethod
    def empty_grounding(cls, times: Optional[int] = None, message: Optional[str] = None) -> "Fault":
        """Simulate Data Cloud / Vector Store returning 0 relevant chunks (empty RAG context)."""
        return cls(
            fault_type=FaultType.EMPTY_GROUNDING,
            trigger=FaultTrigger.N_TIMES if times is not None else FaultTrigger.ALWAYS,
            times=times,
            payload={"chunks": [], "records": [], "total_chunks": 0, "status": "NO_GROUNDING_FOUND"},
            message=message or "Data Cloud vector search returned 0 matching records",
        )

    @classmethod
    def stale_grounding(cls, stale_payload: Any = None, times: Optional[int] = None, message: Optional[str] = None) -> "Fault":
        """Simulate Data Cloud / Vector Store returning outdated or superseded knowledge articles."""
        return cls(
            fault_type=FaultType.STALE_GROUNDING,
            trigger=FaultTrigger.N_TIMES if times is not None else FaultTrigger.ALWAYS,
            times=times,
            payload=stale_payload or {"chunks": [{"text": "[DEPRECATED POLICY] Return window is 14 days", "version": "v1-outdated"}]},
            message=message or "Data Cloud vector index returned stale/deprecated grounding documents",
        )

    def should_trigger(self, fault_invocation_count: int, args_dict: Dict[str, Any]) -> bool:
        """Evaluate if the fault should activate on this fault occurrence index."""
        if self.condition and not self.condition(args_dict):
            return False

        if self.trigger == FaultTrigger.ALWAYS:
            return True
        elif self.trigger == FaultTrigger.N_TIMES:
            return self.times is not None and fault_invocation_count <= self.times
        elif self.trigger == FaultTrigger.AFTER_N_CALLS:
            return self.times is not None and fault_invocation_count > self.times
        return False

    async def apply_async(self) -> Any:
        """Apply the fault to an asynchronous tool call."""
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        if self.fault_type == FaultType.TIMEOUT:
            raise TimeoutError(self.message)
        elif self.fault_type in (FaultType.HTTP_ERROR, FaultType.RATE_LIMIT):
            raise ToolHTTPError(status_code=self.status_code, message=self.message, payload=self.payload)
        elif self.fault_type == FaultType.CUSTOM_EXCEPTION:
            if self.custom_exception:
                raise self.custom_exception
            raise RuntimeError(self.message)
        elif self.fault_type in (FaultType.MALFORMED_DATA, FaultType.POISONED_PAYLOAD, FaultType.EMPTY_GROUNDING, FaultType.STALE_GROUNDING):
            return self.payload
        elif self.fault_type == FaultType.LATENCY:
            return None  # Let real function proceed after delay
        return None

    def apply_sync(self) -> Any:
        """Apply the fault to a synchronous tool call."""
        if self.delay > 0:
            time.sleep(self.delay)

        if self.fault_type == FaultType.TIMEOUT:
            raise TimeoutError(self.message)
        elif self.fault_type in (FaultType.HTTP_ERROR, FaultType.RATE_LIMIT):
            raise ToolHTTPError(status_code=self.status_code, message=self.message, payload=self.payload)
        elif self.fault_type == FaultType.CUSTOM_EXCEPTION:
            if self.custom_exception:
                raise self.custom_exception
            raise RuntimeError(self.message)
        elif self.fault_type in (FaultType.MALFORMED_DATA, FaultType.POISONED_PAYLOAD, FaultType.EMPTY_GROUNDING, FaultType.STALE_GROUNDING):
            return self.payload
        elif self.fault_type == FaultType.LATENCY:
            return None  # Let real function proceed after delay
        return None


class ToolHTTPError(Exception):
    """Raised when an HTTP error fault is simulated for a tool."""
    def __init__(self, status_code: int, message: str, payload: Any = None):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.payload = payload
