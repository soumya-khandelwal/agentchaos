"""Salesforce Agentforce Chaos & Reliability testing module."""

from agent_chaos.salesforce.driver import (
    AgentforceClient,
    AgentforceConfig,
    AgentTurnResult,
)
from agent_chaos.salesforce.gateway import (
    SalesforceChaosGateway,
    SalesforceChaosServer,
)
from agent_chaos.salesforce.hallucination import (
    HallucinationDetector,
    HallucinationReport,
    HallucinationType,
)
from agent_chaos.salesforce.templates import (
    CUSTOMER_SERVICE_SPEC,
    ORDER_SERVICE_SPEC,
    PAYMENT_SERVICE_SPEC,
    PREBUILT_TEMPLATES,
    get_template_spec,
)
from agent_chaos.salesforce.timeout_profiler import (
    LatencyTrial,
    TimeoutProfileReport,
    TimeoutProfiler,
)

from agent_chaos.salesforce.native import (
    APEX_ENGINE_CLS,
    APEX_ENGINE_META,
    CASE_ACTION_CLS,
    CASE_ACTION_META,
    AuditContext,
    AuditReport,
    BaseAuditRule,
    ChannelBudget,
    ChannelEvaluation,
    EntityFabricationRule,
    FalseSuccessRule,
    MultiChannelSLAReport,
    NativeHallucinationAuditor,
    NativeSLAProfiler,
    RuleViolation,
    export_apex_classes,
)

__all__ = [
    "SalesforceChaosGateway",
    "SalesforceChaosServer",
    "HallucinationDetector",
    "HallucinationReport",
    "HallucinationType",
    "TimeoutProfiler",
    "TimeoutProfileReport",
    "LatencyTrial",
    "AgentforceClient",
    "AgentforceConfig",
    "AgentTurnResult",
    "PREBUILT_TEMPLATES",
    "PAYMENT_SERVICE_SPEC",
    "ORDER_SERVICE_SPEC",
    "CUSTOMER_SERVICE_SPEC",
    "get_template_spec",
    "export_apex_classes",
    "APEX_ENGINE_CLS",
    "APEX_ENGINE_META",
    "CASE_ACTION_CLS",
    "CASE_ACTION_META",
    "AuditContext",
    "RuleViolation",
    "AuditReport",
    "BaseAuditRule",
    "FalseSuccessRule",
    "EntityFabricationRule",
    "NativeHallucinationAuditor",
    "ChannelBudget",
    "ChannelEvaluation",
    "MultiChannelSLAReport",
    "NativeSLAProfiler",
]
