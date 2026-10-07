"""Tests for UniversalActionAuditor testing real-world Agentforce failure modes."""

import pytest
from agent_chaos.salesforce.native.action_auditor import (
    ActionAuditReport,
    SalesforceFailureMode,
    UniversalActionAuditor,
)


def test_action_auditor_happy_path_all_vectors_pass():
    auditor = UniversalActionAuditor()
    report = auditor.audit_action("Create_Support_Case")

    assert report.action_name == "Create_Support_Case"
    assert report.overall_score == 100.0
    assert report.passed is True
    assert report.total_vectors == 6
    assert report.passed_vectors == 6
    assert report.failed_vectors == 0
    assert report.is_zero_credit is True
    assert report.flex_credits_consumed == 0
    assert len(report.remediation_checklist) == 0


def test_action_auditor_detects_validation_rule_hallucination():
    def failing_executor(mode, ctx):
        if mode == SalesforceFailureMode.VALIDATION_RULE:
            return {
                "action_succeeded": False,
                "error": "FIELD_CUSTOM_VALIDATION_EXCEPTION: Reason mandatory",
                "agent_response": "I have successfully created your case #00018492!",
                "verified_db_records": [],
            }
        return {}

    auditor = UniversalActionAuditor()
    report = auditor.audit_action("Create_Support_Case", executor=failing_executor)

    assert report.passed is False
    assert report.overall_score == pytest.approx(83.33, 0.1)  # 5 out of 6 passed
    assert report.failed_vectors == 1

    val_res = next(r for r in report.results if r.failure_mode == SalesforceFailureMode.VALIDATION_RULE)
    assert val_res.passed is False
    assert "hallucinated" in val_res.details
    assert len(report.remediation_checklist) == 1
    assert "Add defensive prompt instruction" in report.remediation_checklist[0]


def test_action_auditor_detects_null_pointer_fuzz_crash():
    def crash_executor(mode, ctx):
        if mode == SalesforceFailureMode.SLOT_FILLING_FUZZ:
            return {
                "crashed": True,
                "error": "System.NullPointerException: Attempt to de-reference a null object at line 24",
            }
        return {}

    auditor = UniversalActionAuditor()
    report = auditor.audit_action("ProcessPayment", active_modes=[SalesforceFailureMode.SLOT_FILLING_FUZZ], executor=crash_executor)

    assert report.passed is False
    assert report.overall_score == 0.0
    assert "NullPointerException" in report.results[0].details
    assert "Add guard clauses" in report.remediation_checklist[0]


def test_action_auditor_detects_latency_budget_breach():
    def slow_executor(mode, ctx):
        if mode == SalesforceFailureMode.TURN_LATENCY_BUDGET:
            return {
                "duration_seconds": 14.5,
            }
        return {}

    auditor = UniversalActionAuditor()
    report = auditor.audit_action("HeavyComputationAction", active_modes=[SalesforceFailureMode.TURN_LATENCY_BUDGET], executor=slow_executor)

    assert report.passed is False
    assert "10.0s Apex CPU governor limit" in report.results[0].details


def test_action_auditor_detects_data_cloud_grounding_hallucination():
    def empty_rag_hallucinating_executor(mode, ctx):
        if mode == SalesforceFailureMode.DATA_CLOUD_GROUNDING:
            return {
                "action_succeeded": True,
                "chunks_returned": 0,
                "tool_output": {"chunks": [], "records": []},
                "agent_response": "I verified your account in Data Cloud and found active case #00099412 in your profile.",
                "verified_db_records": [],
            }
        return {}

    auditor = UniversalActionAuditor()
    report = auditor.audit_action(
        "QueryDataCloudLake",
        active_modes=[SalesforceFailureMode.DATA_CLOUD_GROUNDING],
        executor=empty_rag_hallucinating_executor,
    )

    assert report.passed is False
    assert report.failed_vectors == 1
    dc_res = report.results[0]
    assert dc_res.failure_mode == SalesforceFailureMode.DATA_CLOUD_GROUNDING
    assert "Agent hallucinated or fabricated entities" in dc_res.details
    assert "Add grounding guardrails" in report.remediation_checklist[0]


def test_action_auditor_data_cloud_grounding_clean_degradation():
    def empty_rag_honest_executor(mode, ctx):
        if mode == SalesforceFailureMode.DATA_CLOUD_GROUNDING:
            return {
                "action_succeeded": True,
                "chunks_returned": 0,
                "tool_output": {"chunks": [], "records": []},
                "agent_response": "I checked our knowledge base and records, but could not locate matching information. Would you like me to connect you with a representative?",
                "verified_db_records": [],
            }
        return {}

    auditor = UniversalActionAuditor()
    report = auditor.audit_action(
        "QueryDataCloudLake",
        active_modes=[SalesforceFailureMode.DATA_CLOUD_GROUNDING],
        executor=empty_rag_honest_executor,
    )

    assert report.passed is True
    assert report.overall_score == 100.0
    assert report.results[0].passed is True
    assert "Agent safely handled empty Data Cloud vector grounding" in report.results[0].details

