"""Native Salesforce Agentforce & Experience Cloud Chaos Package."""

from agent_chaos.salesforce.native.apex_generator import (
    APEX_ENGINE_CLS,
    APEX_ENGINE_META,
    CASE_ACTION_CLS,
    CASE_ACTION_META,
    export_apex_classes,
)
from agent_chaos.salesforce.native.evaluator import (
    AuditContext,
    AuditReport,
    BaseAuditRule,
    EntityFabricationRule,
    FalseSuccessRule,
    NativeHallucinationAuditor,
    RuleViolation,
)
from agent_chaos.salesforce.native.sla_profiler import (
    ChannelBudget,
    ChannelEvaluation,
    MultiChannelSLAReport,
    NativeSLAProfiler,
)

__all__ = [
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
