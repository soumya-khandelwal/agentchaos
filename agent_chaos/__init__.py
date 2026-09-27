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

from agent_chaos.security import (
    AttackCategory,
    SecurityPayload,
    get_all_payloads,
    get_payload_by_id,
    get_payloads_by_category,
    AttackResult,
    RedTeamReport,
    RedTeamSuite,
)

from agent_chaos.reporting import (
    generate_html_report,
    export_junit_xml,
)

__version__ = "0.3.0"

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
    "AttackCategory",
    "SecurityPayload",
    "get_all_payloads",
    "get_payload_by_id",
    "get_payloads_by_category",
    "AttackResult",
    "RedTeamReport",
    "RedTeamSuite",
    "generate_html_report",
    "export_junit_xml",
]
