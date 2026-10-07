"""Fault types and definitions for Multi-Agent Handoffs and Orchestration."""

from __future__ import annotations

import copy
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class HandoffFaultType(str, Enum):
    DROPPED_CONTEXT = "dropped_context"          # Strips metadata or message history during delegation
    STALE_STATE = "stale_state"                  # Reverts state/memory to an earlier snapshot
    ROUTING_TIMEOUT = "routing_timeout"          # Sub-agent takes too long or fails to respond
    POISONED_HANDOFF = "poisoned_handoff"        # Injects malicious or corrupt payload during handoff
    OUT_OF_ORDER = "out_of_order"                # Transposes or delays message sequencing
    SUBAGENT_EXCEPTION = "subagent_exception"    # Sub-agent crashes ungracefully


class HandoffFault(BaseModel):
    """Specifies a fault to inject during agent-to-agent delegation."""
    fault_type: HandoffFaultType
    from_agent: Optional[str] = None
    to_agent: Optional[str] = None
    delay_seconds: float = 0.0
    stale_state_payload: Optional[Dict[str, Any]] = None
    poison_payload: Optional[str] = None
    error_message: str = "Sub-agent handoff error"
    strip_keys: List[str] = Field(default_factory=list)
    times: Optional[int] = None

    @classmethod
    def drop_context(
        cls,
        strip_keys: Optional[List[str]] = None,
        from_agent: Optional[str] = None,
        to_agent: Optional[str] = None,
    ) -> "HandoffFault":
        return cls(
            fault_type=HandoffFaultType.DROPPED_CONTEXT,
            strip_keys=strip_keys or [],
            from_agent=from_agent,
            to_agent=to_agent,
            error_message="Context metadata stripped during delegation",
        )

    @classmethod
    def routing_timeout(
        cls,
        delay_seconds: float = 5.0,
        from_agent: Optional[str] = None,
        to_agent: Optional[str] = None,
    ) -> "HandoffFault":
        return cls(
            fault_type=HandoffFaultType.ROUTING_TIMEOUT,
            delay_seconds=delay_seconds,
            from_agent=from_agent,
            to_agent=to_agent,
            error_message=f"Sub-agent failed to respond within {delay_seconds}s timeout",
        )

    @classmethod
    def stale_state(
        cls,
        stale_payload: Dict[str, Any],
        from_agent: Optional[str] = None,
        to_agent: Optional[str] = None,
    ) -> "HandoffFault":
        return cls(
            fault_type=HandoffFaultType.STALE_STATE,
            stale_state_payload=stale_payload,
            from_agent=from_agent,
            to_agent=to_agent,
        )

    @classmethod
    def poison_handoff(
        cls,
        payload: str,
        from_agent: Optional[str] = None,
        to_agent: Optional[str] = None,
    ) -> "HandoffFault":
        return cls(
            fault_type=HandoffFaultType.POISONED_HANDOFF,
            poison_payload=payload,
            from_agent=from_agent,
            to_agent=to_agent,
        )
