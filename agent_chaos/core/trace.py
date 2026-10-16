"""Causal Execution Trace and OpenTelemetry GenAI Span Engine."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent_chaos.core.trajectory import ToolCallEvent


class OTelGenAISpan(BaseModel):
    """OpenTelemetry-compliant GenAI and Tool execution span."""
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: Optional[str] = None
    name: str
    kind: str = "INTERNAL"
    start_time_unix_nano: int = Field(default_factory=lambda: int(time.time() * 1e9))
    end_time_unix_nano: int = Field(default_factory=lambda: int(time.time() * 1e9))
    status_code: str = "OK"  # "OK" or "ERROR"
    status_message: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)


class CausalTraceStep(BaseModel):
    """Human-readable causal step in the agent execution narrative."""
    step_index: int
    offset_ms: float
    actor: str  # "AGENT", "TOOL", "CHAOS", "ASSERTION"
    action: str
    details: str
    status: str = "OK"  # "OK", "FAULT", "FAIL"


class EvaluationResult(BaseModel):
    """Standardized result.json contract storing OTel spans, evidence, and verdict."""
    run_id: str = Field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}")
    timestamp: float = Field(default_factory=time.time)
    scenario: str = "default_scenario"
    policy: str = "default_policy"
    verdict: str = "PASS"  # "PASS" or "FAIL"
    passed: bool = True
    first_failed_assertion: Optional[str] = None
    root_cause_evidence: Optional[str] = None
    causal_timeline: List[str] = Field(default_factory=list)
    steps: List[CausalTraceStep] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    spans: List[OTelGenAISpan] = Field(default_factory=list)
    agent_response: Optional[str] = None
    total_duration_ms: float = 0.0

    def to_result_json(self, path: Optional[str] = "result.json") -> str:
        """Serialize evaluation result to standardized result.json."""
        json_data = self.model_dump_json(indent=2)
        if path:
            import os
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True) if os.path.dirname(path) else None
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_data)
        return json_data

    def to_junit_xml(self) -> str:
        """Export result as standard JUnit XML for GitHub Actions & CI/CD."""
        time_sec = self.total_duration_ms / 1000.0
        failures_count = 1 if not self.passed else 0
        failure_tag = ""
        if not self.passed:
            failure_tag = (
                f'<failure message="{self.first_failed_assertion or "Assertion Failed"}" type="BlastRadiusViolation">\n'
                f'  {self.root_cause_evidence or "Evidence not available"}\n'
                f'</failure>'
            )

        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<testsuite name="AgentChaos.{self.scenario}" tests="1" failures="{failures_count}" errors="0" time="{time_sec:.3f}">\n'
            f'  <testcase classname="agentchaos.{self.policy}" name="{self.scenario}" time="{time_sec:.3f}">\n'
            f'    {failure_tag}\n'
            f'  </testcase>\n'
            f'</testsuite>'
        )


class CausalTraceBuilder:
    """Builds OpenTelemetry GenAI spans and causal narrative from recorded events."""

    def __init__(self, trace_id: Optional[str] = None) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex
        self.root_span_id = uuid.uuid4().hex[:16]
        self.spans: List[OTelGenAISpan] = []
        self.steps: List[CausalTraceStep] = []
        self.timeline_strings: List[str] = []
        self._start_time = time.time()

    def build_from_trajectory(
        self,
        events: List[ToolCallEvent],
        scenario_name: str,
        policy_name: str,
        agent_response: Optional[str] = None,
        assertion_error: Optional[Exception] = None,
    ) -> EvaluationResult:
        """Construct full EvaluationResult from trajectory events and assertion outcomes."""
        current_offset = 0.0

        for idx, ev in enumerate(events, start=1):
            current_offset += ev.duration_ms
            span_id = uuid.uuid4().hex[:16]

            # 1. Tool Call Span (OTel GenAI convention)
            status_code = "ERROR" if ev.error else "OK"
            span = OTelGenAISpan(
                trace_id=self.trace_id,
                span_id=span_id,
                parent_span_id=self.root_span_id,
                name=f"gen_ai.tool.{ev.tool_name}",
                kind="CLIENT",
                status_code=status_code,
                status_message=ev.error,
                attributes={
                    "gen_ai.system": "agent_chaos",
                    "gen_ai.tool.name": ev.tool_name,
                    "gen_ai.tool.call.id": f"call_{ev.global_index}",
                    "gen_ai.tool.arguments": ev.arguments,
                    "gen_ai.tool.duration_ms": ev.duration_ms,
                    "chaos.fault_injected": ev.fault_injected.value if ev.fault_injected else None,
                },
            )

            # Record Injected Fault event
            if ev.fault_injected:
                span.events.append({
                    "name": "chaos_fault_injected",
                    "timestamp": int(time.time() * 1e9),
                    "attributes": {
                        "fault.type": ev.fault_injected.value,
                        "fault.error": str(ev.error),
                    },
                })
                # Add to human timeline
                step_str = f"[{current_offset/1000:05.2f}s] ➔ Tool Call #{idx}: {ev.tool_name}({ev.arguments})"
                self.timeline_strings.append(step_str)
                self.steps.append(CausalTraceStep(
                    step_index=len(self.steps) + 1,
                    offset_ms=current_offset,
                    actor="AGENT",
                    action=f"call_{ev.tool_name}",
                    details=str(ev.arguments),
                    status="OK",
                ))

                fault_str = f"[{current_offset/1000:05.2f}s] ⚡ INJECTED FAULT: {ev.fault_injected.value.upper()} ({ev.error})"
                self.timeline_strings.append(fault_str)
                self.steps.append(CausalTraceStep(
                    step_index=len(self.steps) + 1,
                    offset_ms=current_offset,
                    actor="CHAOS",
                    action="inject_fault",
                    details=str(ev.error),
                    status="FAULT",
                ))
            else:
                step_str = f"[{current_offset/1000:05.2f}s] ➔ Tool Call #{idx}: {ev.tool_name} (Status: OK)"
                self.timeline_strings.append(step_str)
                self.steps.append(CausalTraceStep(
                    step_index=len(self.steps) + 1,
                    offset_ms=current_offset,
                    actor="AGENT",
                    action=f"call_{ev.tool_name}",
                    details="Completed successfully",
                    status="OK",
                ))

            self.spans.append(span)

        # Agent response step
        if agent_response:
            resp_str = f"[{current_offset/1000:05.2f}s] 💬 Agent Response: \"{agent_response[:90]}...\""
            self.timeline_strings.append(resp_str)
            self.steps.append(CausalTraceStep(
                step_index=len(self.steps) + 1,
                offset_ms=current_offset,
                actor="AGENT",
                action="respond",
                details=agent_response,
                status="OK",
            ))

        # Root cause and assertion failure identification
        first_failed_assertion = None
        evidence_msg = None
        passed = True

        if assertion_error:
            passed = False
            first_failed_assertion = assertion_error.__class__.__name__
            evidence_msg = str(assertion_error)
            fail_str = f"💥 FIRST ASSERTION FAILED: [{first_failed_assertion}] {evidence_msg}"
            self.timeline_strings.append(fail_str)
            self.steps.append(CausalTraceStep(
                step_index=len(self.steps) + 1,
                offset_ms=current_offset,
                actor="ASSERTION",
                action="assertion_failed",
                details=evidence_msg,
                status="FAIL",
            ))

        findings = []
        if not passed:
            findings.append({
                "assertion": first_failed_assertion,
                "evidence": evidence_msg,
                "severity": "CRITICAL",
            })

        return EvaluationResult(
            scenario=scenario_name,
            policy=policy_name,
            verdict="PASS" if passed else "FAIL",
            passed=passed,
            first_failed_assertion=first_failed_assertion,
            root_cause_evidence=evidence_msg,
            causal_timeline=self.timeline_strings,
            steps=self.steps,
            findings=findings,
            spans=self.spans,
            agent_response=agent_response,
            total_duration_ms=current_offset,
        )
