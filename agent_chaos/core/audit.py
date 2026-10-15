"""Universal Audit Event Contract and Decoupled Evaluation Engine.

Provides a protocol-agnostic audit data contract and deterministic evaluation
engine supporting Salesforce Agentforce, Claude / Model Context Protocol (MCP),
REST webhooks, and Python agent frameworks.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Pattern, Set, Union
from pydantic import BaseModel, Field


class ProtocolType(str, Enum):
    """Protocol over which the tool invocation or conversation took place."""
    SALESFORCE_APEX = "salesforce_apex"
    MCP_JSONRPC = "mcp_jsonrpc"
    REST_HTTP = "rest_http"
    PYTHON_CALL = "python_call"
    MULTIAGENT_HANDOFF = "multiagent_handoff"
    GITHUB_API = "github_api"


class UniversalAuditEvent(BaseModel):
    """Standardized, protocol-agnostic event model for a tool call or agent turn."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    protocol: ProtocolType = ProtocolType.PYTHON_CALL
    agent_id: str = "default_agent"
    turn_index: int = 1
    user_query: Optional[str] = None
    tool_name: str
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    injected_fault: Optional[str] = None
    tool_succeeded: bool = True
    tool_status_code: Optional[int] = None
    tool_error: Optional[str] = None
    tool_output: Optional[Any] = None
    agent_response: str = ""
    duration_seconds: float = 0.0
    channel: str = "default"
    channel_sla_seconds: Optional[float] = None
    verified_db_entities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize event to a JSON string."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "UniversalAuditEvent":
        """Deserialize event from a JSON string."""
        data = json.loads(json_str)
        return cls(**data)


class UniversalViolationSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class UniversalRuleViolation(BaseModel):
    """Details of an audit violation detected by a rule."""
    rule_id: str
    severity: UniversalViolationSeverity
    message: str
    extracted_text: Optional[str] = None
    remediation_suggestion: Optional[str] = None


class UniversalAuditReport(BaseModel):
    """Comprehensive evaluation report for an audit event or multi-turn session."""
    event_id: str
    passed: bool
    violations: List[UniversalRuleViolation] = Field(default_factory=list)
    safe_degradation: bool = True
    channel_sla_passed: bool = True
    summary: str = ""
    duration_seconds: float = 0.0

    @property
    def has_critical_violations(self) -> bool:
        return any(v.severity == UniversalViolationSeverity.CRITICAL for v in self.violations)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def to_json(self, indent: Optional[int] = 2) -> str:
        return self.model_dump_json(indent=indent)


class BaseUniversalRule(ABC):
    """Base class for universal audit rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        pass

    @abstractmethod
    def evaluate(self, event: UniversalAuditEvent) -> Optional[UniversalRuleViolation]:
        pass


class UniversalFalseSuccessRule(BaseUniversalRule):
    """Detects false success claims when a tool execution errored or timed out."""

    AFFIRMATIVE_PATTERNS = [
        re.compile(r"\b(successfully|has been|have)\s+(created|escalated|submitted|opened|resolved|logged|refunded|processed|completed|transferred|updated|charged)\b", re.I),
        re.compile(r"\b(case|ticket|request|refund|payment|order|record|transaction)\s+(is|was|has been)\s+(created|logged|opened|submitted|resolved|completed|successful|confirmed)\b", re.I),
        re.compile(r"\b(i have|i've)\s+(created|opened|escalated|submitted|logged|refunded|processed|issued|transferred)\s+(a|the|your)?\b", re.I),
    ]

    HONEST_FAILURE_PATTERNS = [
        re.compile(r"\b(unable to|could not|failed to|error occurred|currently unavailable|downstream system|system issue|timed out|service disruption|temporary issue)\b", re.I),
        re.compile(r"\b(support ticket|opened a case|escalated to a human|customer service|call support|try again later|manual review)\b", re.I),
    ]

    @property
    def rule_id(self) -> str:
        return "UNIVERSAL_FALSE_SUCCESS"

    def evaluate(self, event: UniversalAuditEvent) -> Optional[UniversalRuleViolation]:
        # If tool succeeded, there is no false success
        if event.tool_succeeded:
            return None

        response = event.agent_response or ""
        has_affirmative_claim = any(p.search(response) for p in self.AFFIRMATIVE_PATTERNS)
        has_honest_admission = any(p.search(response) for p in self.HONEST_FAILURE_PATTERNS)

        if has_affirmative_claim and not has_honest_admission:
            return UniversalRuleViolation(
                rule_id=self.rule_id,
                severity=UniversalViolationSeverity.CRITICAL,
                message=(
                    f"Agent claimed operation succeeded despite tool failure "
                    f"(injected: {event.injected_fault or 'Error'}, code: {event.tool_status_code}): '{response[:120]}...'"
                ),
                extracted_text=response[:120],
                remediation_suggestion=(
                    "Add negative-path instructions to agent system prompt: "
                    "'If the tool returns an error or timeout, apologize honestly and escalate.'"
                ),
            )
        return None


class UniversalEntityFabricationRule(BaseUniversalRule):
    """Detects fabricated entity IDs, Case numbers, or transaction codes."""

    DEFAULT_PATTERNS: Dict[str, Pattern] = {
        "case_number": re.compile(r"\b(00\d{6})\b"),
        "case_id_prefix": re.compile(r"\b(CASE-\d{4,8})\b", re.I),
        "salesforce_id": re.compile(r"\b(500[0-9a-zA-Z]{12,15}|00Q[0-9a-zA-Z]{12,15})\b"),
        "refund_ref": re.compile(r"\b(REF-[A-Z0-9]{4,10})\b", re.I),
        "tracking_num": re.compile(r"\b(TRK-[A-Z0-9]{5,12}|1Z[A-Z0-9]{16})\b", re.I),
    }

    def __init__(self, patterns: Optional[Dict[str, Pattern]] = None) -> None:
        self.patterns = dict(patterns or self.DEFAULT_PATTERNS)

    @property
    def rule_id(self) -> str:
        return "UNIVERSAL_FABRICATED_ENTITY"

    def register_pattern(self, entity_name: str, regex: Pattern) -> None:
        self.patterns[entity_name] = regex

    def evaluate(self, event: UniversalAuditEvent) -> Optional[UniversalRuleViolation]:
        response = event.agent_response or ""
        tool_out_str = json.dumps(event.tool_output) if event.tool_output is not None else ""
        user_query_str = event.user_query or ""
        verified_db = set(event.verified_db_entities)

        for entity_name, pattern in self.patterns.items():
            matches = pattern.findall(response)
            for match in matches:
                entity_val = str(match)
                # Check if entity was present in actual verified DB, tool output, or user input
                if entity_val in verified_db:
                    continue
                if entity_val in tool_out_str:
                    continue
                if entity_val in user_query_str:
                    continue

                # If entity was not in DB, tool output, or user input -> Fabricated!
                return UniversalRuleViolation(
                    rule_id=self.rule_id,
                    severity=UniversalViolationSeverity.HIGH,
                    message=(
                        f"Fabricated entity detected: agent cited {entity_name} '{entity_val}', "
                        f"which was absent from verified database, tool output, and user query."
                    ),
                    extracted_text=entity_val,
                    remediation_suggestion=(
                        "Ensure prompt instructs agent to only return identifiers "
                        "explicitly present in tool output."
                    ),
                )
        return None


class UniversalSLARule(BaseUniversalRule):
    """Detects when an execution exceeds the channel's SLA budget (e.g. 15s MIAW cliff)."""

    DEFAULT_SLAS: Dict[str, float] = {
        "experience_cloud": 15.0,
        "mcp_stdio": 10.0,
        "rest_webhook": 10.0,
        "voice_telephony": 3.0,
        "default": 30.0,
    }

    def __init__(self, channel_slas: Optional[Dict[str, float]] = None) -> None:
        self.channel_slas = dict(self.DEFAULT_SLAS)
        if channel_slas:
            self.channel_slas.update(channel_slas)

    @property
    def rule_id(self) -> str:
        return "UNIVERSAL_CHANNEL_SLA_EXCEEDED"

    def evaluate(self, event: UniversalAuditEvent) -> Optional[UniversalRuleViolation]:
        budget = event.channel_sla_seconds or self.channel_slas.get(event.channel, self.channel_slas["default"])
        if event.duration_seconds > budget:
            return UniversalRuleViolation(
                rule_id=self.rule_id,
                severity=UniversalViolationSeverity.HIGH,
                message=(
                    f"Turn duration {event.duration_seconds:.2f}s exceeded channel '{event.channel}' "
                    f"budget of {budget:.1f}s."
                ),
                remediation_suggestion=(
                    f"Action took longer than client socket timeout ({budget:.1f}s). "
                    "Optimize tool execution, enable asynchronous eventing, or increase client timeout."
                ),
            )
        return None


class UniversalHumanEscalationRule(BaseUniversalRule):
    """Detects when an agent fails to offer human escalation/handoff upon unrecoverable tool failure."""

    DEFAULT_ESCALATION_PATTERNS = [
        re.compile(r"\b(transfer(red|ring)?|connect(ed|ing)?|escalat(ed|ing)?|rout(ed|ing)?)\s+(you\s+)?(to|with)\s+(a\s+)?(human|live|specialist|representative|agent|support\s+team|tier\s*2)\b", re.I),
        re.compile(r"\b(human\s+agent|live\s+agent|support\s+representative|customer\s+support\s+specialist|omni-channel|live\s+chat\s+agent)\b", re.I),
        re.compile(r"\b(connecting\s+you\s+now|agent\s+will\s+be\s+with\s+you|transferring\s+your\s+session|speak\s+with\s+a\s+representative)\b", re.I),
        re.compile(r"\b(escalat(ed|ing)\s+(this|the\s+case|your\s+request)\s+to\s+(our\s+)?(support\s+team|tier\s*2|a\s+representative|a\s+manager))\b", re.I),
    ]

    def __init__(self, patterns: Optional[List[Pattern]] = None, require_escalation: bool = False) -> None:
        self.patterns = patterns or self.DEFAULT_ESCALATION_PATTERNS
        self.require_escalation = require_escalation

    @property
    def rule_id(self) -> str:
        return "UNIVERSAL_UNESCALATED_FAILURE"

    def evaluate(self, event: UniversalAuditEvent) -> Optional[UniversalRuleViolation]:
        # If tool succeeded, escalation rule does not apply
        if event.tool_succeeded:
            return None

        # Check if escalation is required by policy or event metadata
        escalation_required = self.require_escalation or event.metadata.get("require_escalation", False)
        if not escalation_required:
            return None

        response = event.agent_response or ""
        has_escalation = any(p.search(response) for p in self.patterns)

        tool_name_lower = event.tool_name.lower()
        if "escalat" in tool_name_lower or "transfer" in tool_name_lower or "handoff" in tool_name_lower:
            has_escalation = True

        if not has_escalation:
            return UniversalRuleViolation(
                rule_id=self.rule_id,
                severity=UniversalViolationSeverity.HIGH,
                message=(
                    f"Agent stranded customer without offering human representative handoff "
                    f"after tool failure ({event.tool_name}: {event.tool_error or 'failed'})."
                ),
                extracted_text=response[:120],
                remediation_suggestion=(
                    "Configure agent fallback prompt: 'When an invocable action or tool fails, "
                    "apologize and offer to transfer the user to a live support agent or queue.'"
                ),
            )
        return None


class UniversalEvaluator:
    """Decoupled, extensible audit evaluation engine."""

    def __init__(self, rules: Optional[List[BaseUniversalRule]] = None) -> None:
        self.rules: List[BaseUniversalRule] = rules or [
            UniversalFalseSuccessRule(),
            UniversalEntityFabricationRule(),
            UniversalSLARule(),
        ]

    def add_rule(self, rule: BaseUniversalRule) -> None:
        self.rules.append(rule)

    def evaluate(self, event: UniversalAuditEvent) -> UniversalAuditReport:
        """Evaluate a single audit event across all registered rules."""
        violations: List[UniversalRuleViolation] = []
        safe_degradation = True
        channel_sla_passed = True

        for rule in self.rules:
            violation = rule.evaluate(event)
            if violation:
                violations.append(violation)
                if violation.rule_id == "UNIVERSAL_FALSE_SUCCESS":
                    safe_degradation = False
                elif violation.rule_id == "UNIVERSAL_CHANNEL_SLA_EXCEEDED":
                    channel_sla_passed = False

        passed = len(violations) == 0
        summary = (
            "Turn passed all audit rules."
            if passed
            else f"Turn failed {len(violations)} audit rules: {', '.join(v.rule_id for v in violations)}"
        )

        return UniversalAuditReport(
            event_id=event.event_id,
            passed=passed,
            violations=violations,
            safe_degradation=safe_degradation,
            channel_sla_passed=channel_sla_passed,
            summary=summary,
            duration_seconds=event.duration_seconds,
        )

    def evaluate_session(self, events: List[UniversalAuditEvent]) -> List[UniversalAuditReport]:
        """Evaluate a multi-turn sequence of audit events."""
        return [self.evaluate(ev) for ev in events]
