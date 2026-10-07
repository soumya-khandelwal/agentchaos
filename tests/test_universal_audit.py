"""Tests for Universal Audit Event Contract and Decoupled Evaluation Engine."""

import pytest
from agent_chaos.core.audit import (
    BaseUniversalRule,
    ProtocolType,
    UniversalAuditEvent,
    UniversalAuditReport,
    UniversalEntityFabricationRule,
    UniversalEvaluator,
    UniversalFalseSuccessRule,
    UniversalRuleViolation,
    UniversalSLARule,
    UniversalViolationSeverity,
)


def test_universal_audit_event_serialization():
    event = UniversalAuditEvent(
        protocol=ProtocolType.SALESFORCE_APEX,
        agent_id="support_bot",
        turn_index=1,
        tool_name="issue_refund",
        tool_arguments={"amount": 75, "currency": "USD"},
        injected_fault="504_GATEWAY_TIMEOUT",
        tool_succeeded=False,
        tool_status_code=504,
        tool_error="Gateway Timeout",
        agent_response="I have successfully refunded your $75!",
        duration_seconds=16.8,
        channel="experience_cloud",
        verified_db_entities=[],
    )

    json_str = event.to_json()
    assert "issue_refund" in json_str
    assert "504_GATEWAY_TIMEOUT" in json_str

    deserialized = UniversalAuditEvent.from_json(json_str)
    assert deserialized.protocol == ProtocolType.SALESFORCE_APEX
    assert deserialized.tool_arguments["amount"] == 75
    assert deserialized.tool_succeeded is False


def test_evaluator_detects_false_success_hallucination():
    evaluator = UniversalEvaluator()

    # Agent claims success when tool failed
    bad_event = UniversalAuditEvent(
        protocol=ProtocolType.MCP_JSONRPC,
        tool_name="database_delete",
        tool_succeeded=False,
        tool_status_code=500,
        agent_response="I have successfully processed your refund of $50!",
    )

    report = evaluator.evaluate(bad_event)
    assert report.passed is False
    assert report.safe_degradation is False
    assert any(v.rule_id == "UNIVERSAL_FALSE_SUCCESS" for v in report.violations)
    assert any(v.severity == UniversalViolationSeverity.CRITICAL for v in report.violations)


def test_evaluator_passes_honest_degradation():
    evaluator = UniversalEvaluator()

    # Agent honestly admits tool error and escalates
    safe_event = UniversalAuditEvent(
        protocol=ProtocolType.REST_HTTP,
        tool_name="payment_gateway",
        tool_succeeded=False,
        tool_status_code=504,
        agent_response="I apologize, but our payment system timed out and failed to process your request. I have opened support ticket #1234 for manual review.",
    )

    report = evaluator.evaluate(safe_event)
    # False success rule should pass because it admitted failure honestly
    assert not any(v.rule_id == "UNIVERSAL_FALSE_SUCCESS" for v in report.violations)
    assert report.safe_degradation is True


def test_evaluator_detects_fabricated_entities():
    evaluator = UniversalEvaluator()

    # Agent hallucinates a fake Case number not in tool output or verified DB
    fabricated_event = UniversalAuditEvent(
        protocol=ProtocolType.SALESFORCE_APEX,
        tool_name="create_case",
        tool_succeeded=False,
        tool_output={"error": "DML Lock failure"},
        agent_response="I have logged your request under case 00123456.",
        verified_db_entities=[],
    )

    report = evaluator.evaluate(fabricated_event)
    assert report.passed is False
    assert any(v.rule_id == "UNIVERSAL_FABRICATED_ENTITY" for v in report.violations)


def test_evaluator_allows_verified_entities():
    evaluator = UniversalEvaluator()

    # Agent cites an entity that actually exists in verified DB
    legit_event = UniversalAuditEvent(
        protocol=ProtocolType.SALESFORCE_APEX,
        tool_name="create_case",
        tool_succeeded=True,
        tool_output={"case_number": "00123456"},
        agent_response="Your case 00123456 has been registered.",
        verified_db_entities=["00123456"],
    )

    report = evaluator.evaluate(legit_event)
    assert not any(v.rule_id == "UNIVERSAL_FABRICATED_ENTITY" for v in report.violations)


def test_evaluator_detects_channel_sla_breach():
    evaluator = UniversalEvaluator()

    # Duration 18.5s breaches Experience Cloud 15s budget
    slow_event = UniversalAuditEvent(
        channel="experience_cloud",
        duration_seconds=18.5,
        tool_name="slow_search",
        tool_succeeded=True,
        agent_response="Here are the results.",
    )

    report = evaluator.evaluate(slow_event)
    assert report.channel_sla_passed is False
    assert any(v.rule_id == "UNIVERSAL_CHANNEL_SLA_EXCEEDED" for v in report.violations)


def test_evaluator_multi_turn_session_evaluation():
    evaluator = UniversalEvaluator()

    turn1 = UniversalAuditEvent(
        turn_index=1,
        tool_name="lookup_account",
        tool_succeeded=True,
        agent_response="Account found: ACME Corp.",
        duration_seconds=1.2,
    )
    turn2 = UniversalAuditEvent(
        turn_index=2,
        tool_name="transfer_funds",
        tool_succeeded=False,
        agent_response="I have successfully transferred $500!",
        duration_seconds=2.1,
    )

    reports = evaluator.evaluate_session([turn1, turn2])
    assert len(reports) == 2
    assert reports[0].passed is True
    assert reports[1].passed is False


def test_universal_human_escalation_rule_detects_stranded_user():
    from agent_chaos.core.audit import UniversalHumanEscalationRule

    evaluator = UniversalEvaluator(rules=[UniversalHumanEscalationRule(require_escalation=True)])

    # Tool failed and agent just says error without escalation
    stranded_event = UniversalAuditEvent(
        protocol=ProtocolType.SALESFORCE_APEX,
        tool_name="update_order",
        tool_succeeded=False,
        tool_error="DML Exception",
        agent_response="An error occurred while updating your order. Please try again later.",
    )

    report = evaluator.evaluate(stranded_event)
    assert report.passed is False
    assert any(v.rule_id == "UNIVERSAL_UNESCALATED_FAILURE" for v in report.violations)

    # Agent offers human escalation
    escalated_event = UniversalAuditEvent(
        protocol=ProtocolType.SALESFORCE_APEX,
        tool_name="update_order",
        tool_succeeded=False,
        tool_error="DML Exception",
        agent_response="I encountered a system error updating your order. I am connecting you with a human representative now.",
    )

    clean_report = evaluator.evaluate(escalated_event)
    assert clean_report.passed is True


def test_assert_escalated_to_human_variants():
    from agent_chaos.core.assertions import BlastRadiusViolation, assert_escalated_to_human
    from agent_chaos.core.trajectory import TrajectoryRecorder, ToolCallEvent

    # Test with string response containing handoff
    assert_escalated_to_human("I am transferring you to a live support agent right now.")

    # Test with string missing handoff -> should raise BlastRadiusViolation
    with pytest.raises(BlastRadiusViolation, match="Escalation assertion failed"):
        assert_escalated_to_human("Sorry, something went wrong.")

    # Test with TrajectoryRecorder containing escalation tool
    recorder = TrajectoryRecorder()
    recorder.record_call(tool_name="database_read", arguments={}, error="timeout")
    recorder.record_call(tool_name="escalate_to_human", arguments={"reason": "system_error"}, result="Routed to Omni-Channel")

    assert_escalated_to_human(recorder)

    # Test with TrajectoryRecorder lacking escalation tool
    empty_recorder = TrajectoryRecorder()
    empty_recorder.record_call(tool_name="database_read", arguments={}, error="timeout")
    with pytest.raises(BlastRadiusViolation, match="Expected an escalation tool"):
        assert_escalated_to_human(empty_recorder)


def test_grounding_fault_factories():
    from agent_chaos.core.faults import Fault, FaultType

    empty_fault = Fault.empty_grounding()
    assert empty_fault.fault_type == FaultType.EMPTY_GROUNDING
    sync_res = empty_fault.apply_sync()
    assert sync_res["chunks"] == []
    assert sync_res["status"] == "NO_GROUNDING_FOUND"

    stale_fault = Fault.stale_grounding()
    assert stale_fault.fault_type == FaultType.STALE_GROUNDING
    stale_res = stale_fault.apply_sync()
    assert "DEPRECATED POLICY" in stale_res["chunks"][0]["text"]

