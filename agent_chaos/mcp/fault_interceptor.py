"""MCP Fault Interception logic for Model Context Protocol JSON-RPC messages."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from agent_chaos.core.faults import Fault, FaultType
from agent_chaos.core.trajectory import TrajectoryRecorder


class MCPFaultRule(BaseModel):
    """Rule specifying a fault to inject for a specific MCP tool call."""
    tool_name: str
    fault: Fault
    as_mcp_error: bool = True  # True: return {"content": [...], "isError": true}
                              # False: return standard JSON-RPC 2.0 {"error": {...}}

    class Config:
        arbitrary_types_allowed = True


class MCPInterceptorResult(BaseModel):
    """Outcome of evaluating a JSON-RPC message against active fault rules."""
    intercepted: bool
    tool_name: Optional[str] = None
    response_payload: Optional[Dict[str, Any]] = None
    delay: float = 0.0
    pass_through_after_delay: bool = False
    fault_type: Optional[FaultType] = None


class MCPFaultInterceptor:
    """Evaluates incoming MCP JSON-RPC requests and generates synthetic chaos faults."""

    def __init__(self, recorder: Optional[TrajectoryRecorder] = None) -> None:
        self.recorder = recorder or TrajectoryRecorder()
        self._rules: Dict[str, MCPFaultRule] = {}
        self._tool_invocations: Dict[str, int] = {}

    def set_fault(self, tool_name: str, fault: Fault, as_mcp_error: bool = True) -> None:
        """Set a fault rule for a given tool name."""
        rule = MCPFaultRule(tool_name=tool_name, fault=fault, as_mcp_error=as_mcp_error)
        self.add_rule(rule)

    def add_rule(self, rule: MCPFaultRule) -> None:
        """Add an MCP fault rule."""
        self._rules[rule.tool_name] = rule
        self._tool_invocations[rule.tool_name] = 0

    def remove_fault(self, tool_name: str) -> None:
        """Remove a fault rule for a tool."""
        self._rules.pop(tool_name, None)
        self._tool_invocations.pop(tool_name, None)

    def get_rule(self, tool_name: str) -> Optional[MCPFaultRule]:
        """Retrieve the fault rule for a given tool name."""
        return self._rules.get(tool_name)

    def has_fault(self, tool_name: str) -> bool:
        """Check if a tool has an active fault rule."""
        return tool_name in self._rules

    def process_request(self, request: Dict[str, Any]) -> MCPInterceptorResult:
        """Inspect a JSON-RPC request and decide whether to inject a fault.

        If intercepted and not pass-through, generates the synthetic response payload.
        """
        method = request.get("method")
        if method != "tools/call":
            return MCPInterceptorResult(intercepted=False)

        params = request.get("params") or {}
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        req_id = request.get("id")

        if not tool_name or tool_name not in self._rules:
            return MCPInterceptorResult(intercepted=False, tool_name=tool_name)

        rule = self._rules[tool_name]
        fault = rule.fault

        count = self._tool_invocations.get(tool_name, 0) + 1
        self._tool_invocations[tool_name] = count

        if not fault.should_trigger(count, arguments):
            return MCPInterceptorResult(intercepted=False, tool_name=tool_name)

        # Fault is triggered!
        if fault.fault_type == FaultType.LATENCY:
            # Latency fault: apply delay, but allow call to pass through to target server
            return MCPInterceptorResult(
                intercepted=True,
                tool_name=tool_name,
                delay=fault.delay,
                pass_through_after_delay=True,
                fault_type=fault.fault_type,
            )

        # Build synthetic response payload
        error_msg = fault.message
        response_payload: Dict[str, Any]

        if fault.fault_type == FaultType.TIMEOUT:
            msg = fault.message or f"Tool '{tool_name}' execution timed out after {fault.delay}s"
            if rule.as_mcp_error:
                response_payload = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {msg}"}],
                        "isError": True,
                    },
                }
            else:
                response_payload = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": msg,
                    },
                }

        elif fault.fault_type in (FaultType.HTTP_ERROR, FaultType.RATE_LIMIT):
            msg = f"HTTP {fault.status_code}: {fault.message}"
            if rule.as_mcp_error:
                response_payload = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {msg}"}],
                        "isError": True,
                    },
                }
            else:
                response_payload = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": fault.status_code,
                        "message": fault.message,
                        "data": fault.payload,
                    },
                }

        elif fault.fault_type == FaultType.MALFORMED_DATA:
            response_payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": fault.payload if fault.payload is not None else {"corrupted": True, "_incomplete": None},
            }

        elif fault.fault_type == FaultType.POISONED_PAYLOAD:
            text = str(fault.payload) if fault.payload is not None else "Adversarial payload"
            response_payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text}],
                    "isError": False,
                },
            }

        elif fault.fault_type == FaultType.CUSTOM_EXCEPTION:
            msg = fault.message or "Custom tool exception simulated"
            if rule.as_mcp_error:
                response_payload = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Exception: {msg}"}],
                        "isError": True,
                    },
                }
            else:
                response_payload = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": msg,
                    },
                }
        else:
            response_payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Fault simulated: {fault.fault_type}"}],
                    "isError": True,
                },
            }

        # Record the synthetic tool call event in trajectory
        duration_ms = fault.delay * 1000
        self.recorder.record_call(
            tool_name=tool_name,
            arguments=arguments,
            duration_ms=duration_ms,
            fault_injected=fault.fault_type,
            result=response_payload.get("result"),
            error=error_msg,
        )

        return MCPInterceptorResult(
            intercepted=True,
            tool_name=tool_name,
            response_payload=response_payload,
            delay=fault.delay,
            pass_through_after_delay=False,
            fault_type=fault.fault_type,
        )

    def record_pass_through(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        duration_ms: float = 0.0,
        result: Any = None,
        error: Optional[str] = None,
        fault_injected: Optional[FaultType] = None,
    ) -> None:
        """Record a tool call that passed through to the target MCP server."""
        self.recorder.record_call(
            tool_name=tool_name,
            arguments=arguments,
            duration_ms=duration_ms,
            fault_injected=fault_injected,
            result=result,
            error=error,
        )
