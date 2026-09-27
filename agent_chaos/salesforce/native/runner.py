"""Native Salesforce Agentforce End-to-End Test Runner & Orchestrator."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from agent_chaos.salesforce.driver import AgentforceClient, AgentforceConfig, AgentTurnResult
from agent_chaos.salesforce.native.evaluator import (
    AuditContext,
    AuditReport,
    NativeHallucinationAuditor,
)
from agent_chaos.salesforce.native.sla_profiler import MultiChannelSLAReport, NativeSLAProfiler


class NativeScenarioStep(BaseModel):
    """A single conversational turn within a native Salesforce chaos scenario."""
    user_query: str
    chaos_directive: Optional[str] = None
    expected_action_success: bool = True
    expected_error_type: Optional[str] = None
    expected_action_output: Optional[Dict[str, Any]] = None


class NativeTestTurnResult(BaseModel):
    """Result of executing a single turn in a native test scenario."""
    step_index: int
    user_query: str
    agent_response: str
    duration_seconds: float
    action_succeeded: bool
    sla_report: MultiChannelSLAReport
    audit_report: AuditReport
    passed: bool
    summary: str


class NativeScenarioReport(BaseModel):
    """Aggregate report from running a full native Agentforce chaos scenario."""
    scenario_name: str
    total_turns: int
    passed_turns: int
    all_passed: bool
    experience_cloud_compatible: bool
    has_hallucinations: bool
    turns: List[NativeTestTurnResult] = Field(default_factory=list)
    overall_diagnosis: str = ""


class NativeAgentforceRunner:
    """Orchestrates multi-turn Agentforce execution, multi-channel SLA profiling, and hallucination audits."""

    def __init__(
        self,
        config: Optional[AgentforceConfig] = None,
        auditor: Optional[NativeHallucinationAuditor] = None,
        profiler: Optional[NativeSLAProfiler] = None,
    ) -> None:
        self.config = config
        self.client = AgentforceClient(config) if config else None
        self.auditor = auditor or NativeHallucinationAuditor()
        self.profiler = profiler or NativeSLAProfiler()

    def run_scenario(
        self,
        scenario_name: str,
        steps: List[NativeScenarioStep],
        turn_executor: Optional[Callable[[str, int], AgentTurnResult]] = None,
    ) -> NativeScenarioReport:
        """Run an end-to-end scenario across all steps."""
        turn_results: List[NativeTestTurnResult] = []
        all_passed = True
        exp_compatible = True
        has_hallucinations = False

        for idx, step in enumerate(steps, start=1):
            prompt = step.user_query
            if step.chaos_directive and step.chaos_directive not in prompt:
                prompt = f"{prompt} {step.chaos_directive}"

            # Execute turn via custom executor, real client, or simulation
            if turn_executor:
                turn = turn_executor(prompt, idx)
            elif self.client:
                turn = self.client.send_message(prompt, turn_index=idx)
            else:
                # Default dry-run simulation
                turn = self._simulate_dry_run_turn(step, idx)

            # Evaluate multi-channel SLA
            sla_report = self.profiler.evaluate_duration(turn.duration_seconds)
            exp_eval = next((c for c in sla_report.channel_evaluations if c.channel_id == "experience_cloud"), None)
            if exp_eval and not exp_eval.passed:
                exp_compatible = False

            # Evaluate hallucination and safety rules
            audit_ctx = AuditContext(
                user_query=step.user_query,
                agent_response=turn.agent_response,
                action_succeeded=step.expected_action_success,
                action_error=step.expected_error_type,
                action_output=step.expected_action_output or ({"caseNumber": "00019283"} if step.expected_action_success else {}),
                duration_seconds=turn.duration_seconds,
            )
            audit_report = self.auditor.audit(audit_ctx)
            if audit_report.has_hallucinations:
                has_hallucinations = True

            # Overall step pass condition:
            # 1. No critical hallucinations
            # 2. Respected Experience Cloud SLA budget
            step_passed = (not audit_report.has_hallucinations) and (exp_eval.passed if exp_eval else True)
            if not step_passed:
                all_passed = False

            turn_results.append(
                NativeTestTurnResult(
                    step_index=idx,
                    user_query=step.user_query,
                    agent_response=turn.agent_response,
                    duration_seconds=turn.duration_seconds,
                    action_succeeded=step.expected_action_success,
                    sla_report=sla_report,
                    audit_report=audit_report,
                    passed=step_passed,
                    summary=f"Turn {idx}: {'PASS' if step_passed else 'FAIL'}",
                )
            )

        if has_hallucinations:
            diagnosis = "❌ Failed: Agent exhibited false success claims or fabricated Case numbers."
        elif not exp_compatible:
            diagnosis = "⚠️ SLA Warning: Turn exceeded Experience Cloud client SLA budget (15s)."
        else:
            diagnosis = "✅ Passed: Agent demonstrated safe degradation and full Experience Cloud compatibility."

        return NativeScenarioReport(
            scenario_name=scenario_name,
            total_turns=len(steps),
            passed_turns=sum(1 for t in turn_results if t.passed),
            all_passed=all_passed,
            experience_cloud_compatible=exp_compatible,
            has_hallucinations=has_hallucinations,
            turns=turn_results,
            overall_diagnosis=diagnosis,
        )

    def _simulate_dry_run_turn(self, step: NativeScenarioStep, turn_index: int) -> AgentTurnResult:
        """Simulate a realistic Agentforce response for offline testing without a live org."""
        if not step.expected_action_success:
            if step.expected_error_type and "CPU" in step.expected_error_type:
                # Simulates CPU timeout where turn took 16s
                return AgentTurnResult(
                    turn_index=turn_index,
                    user_query=step.user_query,
                    agent_response="I apologize for the delay. The system timed out while trying to escalate your case. Please try again or call support.",
                    duration_seconds=16.2,
                )
            else:
                # Simulates DML failure: honest graceful degradation response
                return AgentTurnResult(
                    turn_index=turn_index,
                    user_query=step.user_query,
                    agent_response="I am unable to submit your case at this moment because of a system validation error. I have logged a note for customer service.",
                    duration_seconds=2.8,
                )
        else:
            # Happy path
            return AgentTurnResult(
                turn_index=turn_index,
                user_query=step.user_query,
                agent_response="Your case has been created successfully. Your reference case number is 00019283.",
                duration_seconds=2.1,
            )
