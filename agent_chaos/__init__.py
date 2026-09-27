"""AgentChaos: Fault injection and blast-radius testing framework for AI Agents."""

from agent_chaos.core import (
    Fault,
    FaultType,
    FaultTrigger,
    ToolHTTPError,
    ToolCallEvent,
    TrajectoryRecorder,
    ChaosHarness,
    chaos_harness,
    get_current_harness,
    BlastRadiusViolation,
    assert_tool_called,
    assert_tool_not_called,
    assert_parameters_match,
    assert_max_retries,
    assert_sequence,
)

from agent_chaos.mcp import (
    MCPChaosProxy,
    MCPFaultInterceptor,
    MCPFaultRule,
    MCPInterceptorResult,
)

__version__ = "0.2.0"

__all__ = [
    "Fault",
    "FaultType",
    "FaultTrigger",
    "ToolHTTPError",
    "ToolCallEvent",
    "TrajectoryRecorder",
    "ChaosHarness",
    "chaos_harness",
    "get_current_harness",
    "BlastRadiusViolation",
    "assert_tool_called",
    "assert_tool_not_called",
    "assert_parameters_match",
    "assert_max_retries",
    "assert_sequence",
    "MCPChaosProxy",
    "MCPFaultInterceptor",
    "MCPFaultRule",
    "MCPInterceptorResult",
]
