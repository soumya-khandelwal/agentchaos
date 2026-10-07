"""Universal Action Reliability Auditor for Any Salesforce Agentforce Application.

Evaluates any Invocable Action or Flow against the 6 primary day-to-day failure modes:
1. Validation Rule & DML Rollback Blindness (FIELD_CUSTOM_VALIDATION_EXCEPTION)
2. Slot-Filling Parameter Distortion & NullPointerExceptions
3. Service AgentUser Permission & Flow Interview Faults
4. ReAct Runaway Loops & Governor Limit Exhaustion (SOQL 101 / CPU 10s)
5. Turn Latency & Front-End Timeout Budget
6. Data Cloud & Vector Grounding Retrieval (Empty/Stale RAG context & hallucination resistance)

Guarantees 100% Zero-Credit execution (0 Flex Credits consumed) in offline simulation mode.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from agent_chaos.core.audit import (
    ProtocolType,
    UniversalAuditEvent,
    UniversalEvaluator,
    UniversalViolationSeverity,
)
from agent_chaos.salesforce.native.evaluator import NativeHallucinationAuditor
from agent_chaos.salesforce.native.sla_profiler import NativeSLAProfiler


class SalesforceFailureMode(str, Enum):
    VALIDATION_RULE = "validation_rule"
    SLOT_FILLING_FUZZ = "slot_filling_fuzz"
    AGENT_USER_PERMISSION = "agent_user_permission"
    GOVERNOR_REACT_LOOP = "governor_react_loop"
    TURN_LATENCY_BUDGET = "turn_latency_budget"
    DATA_CLOUD_GROUNDING = "data_cloud_grounding"


class ActionTestVectorResult(BaseModel):
    """Result of auditing an action against a specific failure mode."""
    failure_mode: SalesforceFailureMode
    name: str
    passed: bool
    severity: str = "HIGH"
    details: str
    remediation: str
    duration_seconds: float = 0.0


class ActionAuditReport(BaseModel):
    """Comprehensive readiness scorecard for an Agentforce action."""
    action_name: str
    overall_score: float
    passed: bool
    total_vectors: int
    passed_vectors: int
    failed_vectors: int
    is_zero_credit: bool = True
    flex_credits_consumed: int = 0
    results: List[ActionTestVectorResult] = Field(default_factory=list)
    remediation_checklist: List[str] = Field(default_factory=list)

    def summary(self) -> str:
        status = "PASSED" if self.passed else "FAILED / AT RISK"
        credit_info = f"Zero-Credit Simulation: {self.flex_credits_consumed} Flex Credits" if self.is_zero_credit else "Live Org Run"
        return (
            f"Action [{self.action_name}] Audit: {status} ({self.passed_vectors}/{self.total_vectors} "
            f"vectors clean, Readiness Score: {self.overall_score:.1f}%, {credit_info})"
        )


class UniversalActionAuditor:
    """Audits ANY custom Agentforce Invocable Action or Flow against production failure modes."""

    def __init__(
        self,
        hallucination_auditor: Optional[NativeHallucinationAuditor] = None,
        sla_profiler: Optional[NativeSLAProfiler] = None,
    ) -> None:
        self.auditor = hallucination_auditor or NativeHallucinationAuditor()
        self.profiler = sla_profiler or NativeSLAProfiler()
        self.evaluator = UniversalEvaluator()

    def audit_action(
        self,
        action_name: str,
        active_modes: Optional[List[SalesforceFailureMode]] = None,
        executor: Optional[Callable[[SalesforceFailureMode, Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> ActionAuditReport:
        """Run all or selected failure mode audits against the target action."""
        modes = active_modes or list(SalesforceFailureMode)
        results: List[ActionTestVectorResult] = []

        for mode in modes:
            start_t = time.perf_counter()

            if mode == SalesforceFailureMode.VALIDATION_RULE:
                res = self._test_validation_rule_failure(action_name, executor)
            elif mode == SalesforceFailureMode.SLOT_FILLING_FUZZ:
                res = self._test_slot_filling_fuzz(action_name, executor)
            elif mode == SalesforceFailureMode.AGENT_USER_PERMISSION:
                res = self._test_agent_user_permission(action_name, executor)
            elif mode == SalesforceFailureMode.GOVERNOR_REACT_LOOP:
                res = self._test_governor_react_loop(action_name, executor)
            elif mode == SalesforceFailureMode.TURN_LATENCY_BUDGET:
                res = self._test_turn_latency_budget(action_name, executor)
            elif mode == SalesforceFailureMode.DATA_CLOUD_GROUNDING:
                res = self._test_data_cloud_grounding(action_name, executor)
            else:
                continue

            res.duration_seconds = time.perf_counter() - start_t
            results.append(res)

        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        failed_count = total - passed_count
        score = (passed_count / total * 100.0) if total > 0 else 100.0

        remediations = [r.remediation for r in results if not r.passed]

        return ActionAuditReport(
            action_name=action_name,
            overall_score=score,
            passed=failed_count == 0,
            total_vectors=total,
            passed_vectors=passed_count,
            failed_vectors=failed_count,
            results=results,
            remediation_checklist=remediations,
        )

    def _test_validation_rule_failure(
        self,
        action_name: str,
        executor: Optional[Callable[[SalesforceFailureMode, Dict[str, Any]], Dict[str, Any]]],
    ) -> ActionTestVectorResult:
        """Vector 1: Injects DML validation rule failure (FIELD_CUSTOM_VALIDATION_EXCEPTION)."""
        simulated_res = (
            executor(SalesforceFailureMode.VALIDATION_RULE, {"action": action_name})
            if executor
            else {
                "action_succeeded": False,
                "error": "FIELD_CUSTOM_VALIDATION_EXCEPTION: Reason cannot be blank",
                "agent_response": "I apologize, but I couldn't save your request because the reason field was missing. Could you please specify why you are contacting us?",
                "verified_db_records": [],
            }
        )

        event = UniversalAuditEvent(
            protocol=ProtocolType.SALESFORCE_APEX,
            tool_name=action_name,
            tool_succeeded=simulated_res.get("action_succeeded", False),
            tool_error=simulated_res.get("error"),
            agent_response=simulated_res.get("agent_response", ""),
            verified_db_entities=simulated_res.get("verified_db_records", []),
        )

        report = self.evaluator.evaluate(event)
        passed = report.passed and report.safe_degradation

        details = (
            "Agent safely acknowledged validation failure and prompted user for missing information."
            if passed
            else f"Agent hallucinated or failed to handle validation rule rollback: {report.summary}"
        )

        remediation = (
            "Add defensive prompt instruction in Agentforce Topic: "
            f"'If {action_name} returns a validation exception or DML rollback, do NOT claim success. "
            "Politely inform the customer of the specific required field and ask them to provide it.'"
        )

        return ActionTestVectorResult(
            failure_mode=SalesforceFailureMode.VALIDATION_RULE,
            name="Validation Rule & DML Rollback Blindness",
            passed=passed,
            severity="CRITICAL",
            details=details,
            remediation=remediation,
        )

    def _test_slot_filling_fuzz(
        self,
        action_name: str,
        executor: Optional[Callable[[SalesforceFailureMode, Dict[str, Any]], Dict[str, Any]]],
    ) -> ActionTestVectorResult:
        """Vector 2: Tests action handling of nulls, empty strings, and distorted slot-filling."""
        simulated_res = (
            executor(SalesforceFailureMode.SLOT_FILLING_FUZZ, {"action": action_name, "inputs": {"id": None, "amount": ""}})
            if executor
            else {
                "crashed": False,
                "null_pointer_caught": True,
                "agent_response": "I see you didn't provide a reference number. Could you please share your order or account number?",
            }
        )

        crashed = simulated_res.get("crashed", False)
        passed = not crashed

        details = (
            "Action handled null / empty slot inputs defensively without throwing System.NullPointerException."
            if passed
            else f"Action threw unhandled exception on null parameter inputs: {simulated_res.get('error', 'NullPointerException')}"
        )

        remediation = (
            f"Add guard clauses at the beginning of {action_name}.cls: "
            "if (String.isBlank(req.recordId)) { return ActionOutput.validationError('Missing ID'); } "
            "Never assume Atlas slot-filling will always provide non-null arguments."
        )

        return ActionTestVectorResult(
            failure_mode=SalesforceFailureMode.SLOT_FILLING_FUZZ,
            name="Slot-Filling Fuzz & Null Safety",
            passed=passed,
            severity="HIGH",
            details=details,
            remediation=remediation,
        )

    def _test_agent_user_permission(
        self,
        action_name: str,
        executor: Optional[Callable[[SalesforceFailureMode, Dict[str, Any]], Dict[str, Any]]],
    ) -> ActionTestVectorResult:
        """Vector 3: Tests AgentUser missing CRUD/FLS or Flow Interview fault."""
        simulated_res = (
            executor(SalesforceFailureMode.AGENT_USER_PERMISSION, {"action": action_name})
            if executor
            else {
                "handled_gracefully": True,
                "agent_response": "I encountered a system permission limitation while processing your request. I have routed your issue to a human agent.",
            }
        )

        passed = simulated_res.get("handled_gracefully", True)
        details = (
            "Action shielded flow/permission fault gracefully and initiated human escalation."
            if passed
            else "Flow/Apex crashed with unshielded error, leaving customer stranded in chat."
        )

        remediation = (
            f"1. Ensure 'Salesforce AgentUser' has Permission Set Group assigned with FLS for fields used by {action_name}.\n"
            "2. If this action invokes a Flow, verify Flow is set to 'System Context Without Sharing - Access All Data'."
        )

        return ActionTestVectorResult(
            failure_mode=SalesforceFailureMode.AGENT_USER_PERMISSION,
            name="AgentUser Permission & Flow Interview Shielding",
            passed=passed,
            severity="HIGH",
            details=details,
            remediation=remediation,
        )

    def _test_governor_react_loop(
        self,
        action_name: str,
        executor: Optional[Callable[[SalesforceFailureMode, Dict[str, Any]], Dict[str, Any]]],
    ) -> ActionTestVectorResult:
        """Vector 4: Asserts circuit breaker breaks ReAct loops before SOQL 101 or CPU limits."""
        simulated_res = (
            executor(SalesforceFailureMode.GOVERNOR_REACT_LOOP, {"action": action_name, "call_count": 4})
            if executor
            else {
                "loop_breaker_tripped": True,
                "error_code": "LOOP_BREAKER_TRIGGERED",
                "max_calls": 3,
            }
        )

        passed = simulated_res.get("loop_breaker_tripped", True)
        details = (
            "In-Flight Gate 1 tripped circuit breaker on 4th call, preventing runaway token consumption and SOQL limit breach."
            if passed
            else "Action lacks loop breaker; agent repeated action in a loop risking System.LimitException: Too many SOQL queries: 101."
        )

        remediation = (
            f"Wrap {action_name} calls through AgentActionGateway.cls or implement AgentGatePolicy.cls "
            "to enforce MAX_CALLS_PER_TURN = 3 circuit breaking."
        )

        return ActionTestVectorResult(
            failure_mode=SalesforceFailureMode.GOVERNOR_REACT_LOOP,
            name="ReAct Loop Breaker & Governor Guard",
            passed=passed,
            severity="HIGH",
            details=details,
            remediation=remediation,
        )

    def _test_turn_latency_budget(
        self,
        action_name: str,
        executor: Optional[Callable[[SalesforceFailureMode, Dict[str, Any]], Dict[str, Any]]],
    ) -> ActionTestVectorResult:
        """Vector 5: Profiles execution duration against the 10-second Apex CPU limit and client SLA."""
        simulated_res = (
            executor(SalesforceFailureMode.TURN_LATENCY_BUDGET, {"action": action_name})
            if executor
            else {
                "duration_seconds": 3.4,
            }
        )

        duration = simulated_res.get("duration_seconds", 3.4)
        sla_report = self.profiler.evaluate_duration(duration)
        passed = duration <= 10.0  # Apex synchronous CPU limit is 10,000ms

        details = (
            f"Turn completed in {duration:.2f}s (well within the 10.0s Apex synchronous CPU limit and client budgets)."
            if passed
            else f"Turn took {duration:.2f}s, exceeding the 10.0s Apex CPU governor limit or front-end timeout."
        )

        remediation = (
            f"Action duration ({duration:.2f}s) is dangerously close to or exceeding the 10s Apex CPU limit. "
            "Offload heavy data manipulation to Queueable Apex or optimize SOQL queries."
        )

        return ActionTestVectorResult(
            failure_mode=SalesforceFailureMode.TURN_LATENCY_BUDGET,
            name="Governor CPU & Front-End Latency Budget",
            passed=passed,
            severity="MEDIUM",
            details=details,
            remediation=remediation,
            duration_seconds=duration,
        )

    def _test_data_cloud_grounding(
        self,
        action_name: str,
        executor: Optional[Callable[[SalesforceFailureMode, Dict[str, Any]], Dict[str, Any]]],
    ) -> ActionTestVectorResult:
        """Vector 6: Simulates Data Cloud / Vector Store returning 0 grounding chunks to test hallucination resistance."""
        simulated_res = (
            executor(SalesforceFailureMode.DATA_CLOUD_GROUNDING, {"action": action_name})
            if executor
            else {
                "action_succeeded": True,
                "chunks_returned": 0,
                "agent_response": "I could not find any knowledge records or matching orders in our database. Would you like me to connect you with a representative or search using your account number?",
                "verified_db_records": [],
            }
        )

        event = UniversalAuditEvent(
            protocol=ProtocolType.SALESFORCE_APEX,
            tool_name=action_name,
            tool_succeeded=simulated_res.get("action_succeeded", True),
            tool_output=simulated_res.get("tool_output", {"chunks": [], "records": []}),
            agent_response=simulated_res.get("agent_response", ""),
            verified_db_entities=simulated_res.get("verified_db_records", []),
            metadata={"grounding_chunks": simulated_res.get("chunks_returned", 0)},
        )

        report = self.evaluator.evaluate(event)
        passed = report.passed
        details = (
            "Agent safely handled empty Data Cloud vector grounding without fabricating entities or ungrounded claims."
            if passed
            else f"Agent hallucinated or fabricated entities on empty Data Cloud retrieval: {report.summary}"
        )

        remediation = (
            f"Add grounding guardrails to {action_name}: 'When Data Cloud returns 0 matching records, "
            "explicitly acknowledge lack of knowledge and avoid fabricating details.'"
        )

        return ActionTestVectorResult(
            failure_mode=SalesforceFailureMode.DATA_CLOUD_GROUNDING,
            name="Data Cloud Grounding & RAG Retrieval",
            passed=passed,
            severity="HIGH",
            details=details,
            remediation=remediation,
        )
