"""Multi-Agent Handoff Interception Router and Trajectory Recorder."""

from __future__ import annotations

import copy
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from agent_chaos.multiagent.faults import HandoffFault, HandoffFaultType


class HandoffEvent(BaseModel):
    """Represents a recorded agent-to-agent delegation event."""
    hop_index: int
    from_agent: str
    to_agent: str
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)
    state: Dict[str, Any] = Field(default_factory=dict)
    injected_fault: Optional[HandoffFaultType] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    response: Optional[Any] = None
    timestamp: float = Field(default_factory=time.time)


class MultiAgentChaosHarness:
    """Manages multi-agent orchestration fault injection, routing, and trajectory recording."""

    def __init__(self) -> None:
        self.handoff_events: List[HandoffEvent] = []
        self._fault_map: Dict[str, HandoffFault] = {}
        self._fault_counts: Dict[str, int] = {}

    def set_handoff_fault(
        self,
        target_agent: str,
        fault: HandoffFault,
        from_agent: Optional[str] = None,
    ) -> None:
        """Assign a fault rule when delegating to a target sub-agent."""
        key = f"{from_agent}->{target_agent}" if from_agent else target_agent
        self._fault_map[key] = fault
        self._fault_counts[key] = 0

    def remove_handoff_fault(self, target_agent: str, from_agent: Optional[str] = None) -> None:
        key = f"{from_agent}->{target_agent}" if from_agent else target_agent
        self._fault_map.pop(key, None)
        self._fault_counts.pop(key, None)

    def route_handoff(
        self,
        from_agent: str,
        to_agent: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        state: Optional[Dict[str, Any]] = None,
        agent_executor: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], Any]] = None,
    ) -> Any:
        """Execute a handoff between two agents with chaos evaluation."""
        hop_idx = len(self.handoff_events) + 1
        active_ctx = copy.deepcopy(context) if context else {}
        active_state = copy.deepcopy(state) if state else {}
        active_msg = message

        # Look up fault
        specific_key = f"{from_agent}->{to_agent}"
        fault = self._fault_map.get(specific_key) or self._fault_map.get(to_agent)

        injected: Optional[HandoffFaultType] = None
        error_msg: Optional[str] = None
        res: Optional[Any] = None
        start_t = time.perf_counter()

        try:
            if fault:
                injected = fault.fault_type
                count = self._fault_counts.get(specific_key if specific_key in self._fault_map else to_agent, 0) + 1
                self._fault_counts[specific_key if specific_key in self._fault_map else to_agent] = count

                if fault.fault_type == HandoffFaultType.DROPPED_CONTEXT:
                    if fault.strip_keys:
                        for k in fault.strip_keys:
                            active_ctx.pop(k, None)
                    else:
                        active_ctx.clear()

                elif fault.fault_type == HandoffFaultType.STALE_STATE:
                    if fault.stale_state_payload:
                        active_state = copy.deepcopy(fault.stale_state_payload)

                elif fault.fault_type == HandoffFaultType.POISONED_HANDOFF:
                    if fault.poison_payload:
                        active_msg = fault.poison_payload

                elif fault.fault_type == HandoffFaultType.ROUTING_TIMEOUT:
                    raise TimeoutError(fault.error_message)

                elif fault.fault_type == HandoffFaultType.SUBAGENT_EXCEPTION:
                    raise RuntimeError(fault.error_message)

            # If agent executor provided, call it
            if agent_executor:
                res = agent_executor(active_msg, active_ctx, active_state)
            else:
                res = f"Agent [{to_agent}] processed message: '{active_msg}'"

            return res

        except Exception as exc:
            error_msg = str(exc)
            raise

        finally:
            duration_ms = (time.perf_counter() - start_t) * 1000
            event = HandoffEvent(
                hop_index=hop_idx,
                from_agent=from_agent,
                to_agent=to_agent,
                message=active_msg,
                context=active_ctx,
                state=active_state,
                injected_fault=injected,
                duration_ms=duration_ms,
                error=error_msg,
                response=res,
            )
            self.handoff_events.append(event)

    def total_hops(self) -> int:
        return len(self.handoff_events)

    def get_events_for_agent(self, agent_name: str) -> List[HandoffEvent]:
        return [e for e in self.handoff_events if e.to_agent == agent_name or e.from_agent == agent_name]

    def reset(self) -> None:
        self.handoff_events.clear()
        self._fault_counts.clear()
