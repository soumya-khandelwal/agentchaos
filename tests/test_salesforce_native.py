"""Tests for Native Salesforce Agentforce & Experience Cloud extensible architecture."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
import pytest

from agent_chaos.salesforce.native.apex_generator import export_apex_classes
from agent_chaos.salesforce.native.evaluator import (
    AuditContext,
    BaseAuditRule,
    EntityFabricationRule,
    FalseSuccessRule,
    NativeHallucinationAuditor,
    RuleViolation,
)
from agent_chaos.salesforce.native.sla_profiler import (
    ChannelBudget,
    NativeSLAProfiler,
)


# ============================================================================
# 1. Apex Generator & Metadata Tests
# ============================================================================

def test_export_apex_classes() -> None:
    """Validate generating deployable Apex classes and metadata."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        created = export_apex_classes(tmp_dir)

        assert "AgentChaosEngine.cls" in created
        assert "AgentChaosEngine.cls-meta.xml" in created
        assert "CaseSupportChaosAction.cls" in created
        assert "CaseSupportChaosAction.cls-meta.xml" in created

        engine_content = Path(created["AgentChaosEngine.cls"]).read_text()
        assert "public with sharing class AgentChaosEngine" in engine_content
        assert "CPU_TIMEOUT" in engine_content
        assert "DML_EXCEPTION" in engine_content
        assert "SOQL_LIMIT" in engine_content

        action_content = Path(created["CaseSupportChaosAction.cls"]).read_text()
        assert "@InvocableMethod" in action_content
        assert "AgentChaosEngine.evaluate" in action_content


# ============================================================================
# 2. Extensible Hallucination & Safety Auditor Tests
# ============================================================================

def test_auditor_detects_false_success_claim() -> None:
    """Agent claiming case was created when Apex action failed."""
    auditor = NativeHallucinationAuditor()

    ctx = AuditContext(
        user_query="My shipment arrived completely broken, log a critical ticket",
        agent_response="I have successfully created a new case for you! Our team will reach out.",
        action_succeeded=False,
        action_error="DML Exception: FIELD_CUSTOM_VALIDATION_EXCEPTION",
        duration_seconds=3.2,
    )

    report = auditor.audit(ctx)
    assert report.passed is False
    assert report.has_hallucinations is True
    assert any(v.rule_name == "FALSE_SUCCESS" for v in report.violations)


def test_auditor_detects_fabricated_salesforce_case_number() -> None:
    """Agent inventing an 8-digit Salesforce Case number (e.g. 00019281) not in output."""
    auditor = NativeHallucinationAuditor()

    ctx = AuditContext(
        user_query="Can you escalate this?",
        agent_response="I've escalated your ticket. Your reference case number is 00049281.",
        action_succeeded=False,
        action_error="CPU timeout",
        action_output={},  # No caseNumber in output!
        duration_seconds=4.0,
    )

    report = auditor.audit(ctx)
    assert report.passed is False
    assert report.has_hallucinations is True
    assert any(v.rule_name == "FABRICATED_ENTITY" for v in report.violations)
    assert any(v.extracted_text == "00049281" for v in report.violations)


def test_auditor_allows_legitimate_entity_present_in_output() -> None:
    """When action succeeds and returns caseNumber 00018273, agent mentioning it must pass."""
    auditor = NativeHallucinationAuditor()

    ctx = AuditContext(
        user_query="Log a case",
        agent_response="Your case has been logged under case number 00018273.",
        action_succeeded=True,
        action_output={"caseId": "5000000000001", "caseNumber": "00018273"},
        duration_seconds=2.1,
    )

    report = auditor.audit(ctx)
    assert report.passed is True
    assert len(report.violations) == 0


def test_auditor_extensibility_custom_entity_registration() -> None:
    """Demonstrate registering a custom entity pattern (e.g. Custom Invoice ID: INV-9901)."""
    auditor = NativeHallucinationAuditor()

    # Register custom pattern dynamically
    auditor.register_custom_entity("custom_invoice", re.compile(r"\b(INV-\d{4,6})\b"))

    ctx = AuditContext(
        user_query="Refund my invoice",
        agent_response="I could not process the refund, but invoice INV-88291 has been marked.",
        action_succeeded=False,
        action_output={},  # INV-88291 was never in output or query
    )

    report = auditor.audit(ctx)
    assert report.passed is False
    assert any(v.extracted_text == "INV-88291" for v in report.violations)


def test_auditor_extensibility_custom_rule_plugin() -> None:
    """Demonstrate plugging in a completely new custom domain audit rule."""
    class SecurityDisavowalRule(BaseAuditRule):
        @property
        def name(self) -> str:
            return "NO_INTERNAL_DISCLOSURE"

        def evaluate(self, ctx: AuditContext) -> RuleViolation | None:
            if "validation rule" in ctx.agent_response.lower() or "custom field" in ctx.agent_response.lower():
                return RuleViolation(
                    rule_name=self.name,
                    severity="MEDIUM",
                    message="Agent leaked internal Salesforce schema details to customer",
                )
            return None

    auditor = NativeHallucinationAuditor()
    auditor.add_rule(SecurityDisavowalRule())

    ctx = AuditContext(
        user_query="Help me",
        agent_response="Unable to create case: custom validation rule VR_Case_Mandatory_Tier failed on Account.",
        action_succeeded=False,
    )

    report = auditor.audit(ctx)
    assert report.passed is False
    assert any(v.rule_name == "NO_INTERNAL_DISCLOSURE" for v in report.violations)


def test_auditor_safe_graceful_degradation() -> None:
    """Agent admitting failure honestly must be marked as safe_degradation."""
    auditor = NativeHallucinationAuditor()

    ctx = AuditContext(
        user_query="Submit urgent ticket",
        agent_response="I apologize, but our system is currently unavailable due to an unexpected error. Please call customer service.",
        action_succeeded=False,
        action_error="System.LimitException",
    )

    report = auditor.audit(ctx)
    assert report.passed is True
    assert report.safe_degradation is True


# ============================================================================
# 3. Extensible Multi-Channel SLA Profiler Tests
# ============================================================================

def test_sla_profiler_experience_cloud_discrepancy() -> None:
    """Verify SLA profiler detects Builder pass (45s) vs Experience Cloud drop (15s)."""
    profiler = NativeSLAProfiler()

    # Turn duration: 18.0s (exceeds Experience Cloud 15s, but under Builder 45s)
    report = profiler.evaluate_duration(18.0)

    assert report.has_discrepancy is True
    assert "Discrepancy Alert!" in report.diagnosis

    exp_eval = next(c for c in report.channel_evaluations if c.channel_id == "experience_cloud")
    bld_eval = next(c for c in report.channel_evaluations if c.channel_id == "builder")

    assert exp_eval.passed is False
    assert exp_eval.risk_level == "BREACHED"
    assert bld_eval.passed is True
    assert bld_eval.risk_level == "SAFE"


def test_sla_profiler_custom_channel_registration() -> None:
    """Verify extending the SLA profiler with custom channels (e.g. Internal Portal: 8s)."""
    profiler = NativeSLAProfiler()
    profiler.register_channel(
        channel_id="internal_portal",
        display_name="Internal Partner Portal",
        sla_seconds=8.0,
        description="Fast internal partner intranet SLA",
    )

    # 10s duration passes Builder and Experience Cloud, but breaches Internal Portal
    report = profiler.evaluate_duration(10.0)
    portal_eval = next(c for c in report.channel_evaluations if c.channel_id == "internal_portal")

    assert portal_eval.passed is False
    assert portal_eval.risk_level == "BREACHED"


# ============================================================================
# 4. Native Agentforce Runner & HTML Reporting Tests
# ============================================================================

def test_native_runner_dry_run_and_reporting() -> None:
    """Test full multi-turn native scenario run and visual HTML export."""
    from agent_chaos.salesforce.native.runner import (
        NativeAgentforceRunner,
        NativeScenarioStep,
    )
    from agent_chaos.salesforce.native.reporting import generate_native_html_report

    runner = NativeAgentforceRunner()

    steps = [
        NativeScenarioStep(
            user_query="Please log a case for damaged goods",
            chaos_directive="chaos-dml@test.com",
            expected_action_success=False,
            expected_error_type="DML Exception",
        ),
        NativeScenarioStep(
            user_query="Can you escalate it now?",
            chaos_directive="[CHAOS_CPU_TIMEOUT]",
            expected_action_success=False,
            expected_error_type="Apex CPU timeout",
        ),
    ]

    report = runner.run_scenario("Damaged Goods Escalation Flow", steps)

    assert report.total_turns == 2
    assert len(report.turns) == 2
    # Turn 1 passed via safe degradation, Turn 2 breached Experience Cloud SLA (16.2s > 15s)
    assert report.turns[0].passed is True
    assert report.turns[1].passed is False
    assert report.experience_cloud_compatible is False

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_file:
        html_path = generate_native_html_report(report, tmp_file.name)
        assert Path(html_path).exists()
        content = Path(html_path).read_text()
        assert "Agentforce Native Reliability Report" in content
        assert "Damaged Goods Escalation Flow" in content
        assert "Experience Cloud" in content
        assert "Turn #1" in content
        assert "Turn #2" in content

