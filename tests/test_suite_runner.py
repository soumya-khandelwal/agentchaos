"""Unit tests for NativeSuiteRunner and ScenarioSpec YAML parser."""

import pytest
from pathlib import Path
from agent_chaos.salesforce.native.suite_parser import ScenarioSpec, ScenarioTurn, ScenarioExpectation
from agent_chaos.salesforce.native.suite_runner import NativeSuiteRunner


def test_parse_scenario_spec_from_yaml(tmp_path: Path):
    yaml_content = """
scenario: "Test Order Chaos"
agent: "Customer_Support_Agent"
channel: "experience_cloud"
description: "Testing scenario parser"
turns:
  - turn: 1
    user_query: "Check status of order 123"
    chaos:
      directive: "none"
    expectations:
      expected_topic: "Order_Status"
      action_called: "get_order"
      action_must_succeed: true
      max_duration_seconds: 10.0
  - turn: 2
    user_query: "Cancel order 123"
    chaos:
      directive: "[CHAOS_DML]"
    expectations:
      expected_topic: "Order_Status"
      action_must_succeed: false
"""
    spec_file = tmp_path / "test_scenario.yaml"
    spec_file.write_text(yaml_content, encoding="utf-8")

    spec = ScenarioSpec.from_yaml_file(spec_file)
    assert spec.scenario == "Test Order Chaos"
    assert spec.agent == "Customer_Support_Agent"
    assert spec.channel == "experience_cloud"
    assert len(spec.turns) == 2

    turn1 = spec.turns[0]
    assert turn1.turn == 1
    assert turn1.user_query == "Check status of order 123"
    assert turn1.expectations.action_must_succeed is True
    assert turn1.expectations.max_duration_seconds == 10.0

    turn2 = spec.turns[1]
    assert turn2.turn == 2
    assert turn2.chaos_directive == "[CHAOS_DML]"
    assert turn2.expectations.action_must_succeed is False


def test_suite_runner_simulated_execution(tmp_path: Path):
    spec = ScenarioSpec(
        scenario="Simulated Delivery Escalation",
        agent="Customer_Support_Agent",
        channel="experience_cloud",
        turns=[
            ScenarioTurn(
                turn=1,
                user_query="Please create a support case for broken parcel",
                chaos_directive=None,
                expectations=ScenarioExpectation(
                    action_must_succeed=True,
                    max_duration_seconds=15.0,
                ),
            ),
            ScenarioTurn(
                turn=2,
                user_query="Please create a case with chaos-dml@test.com",
                chaos_directive="[CHAOS_DML]",
                expectations=ScenarioExpectation(
                    action_must_succeed=False,
                    max_duration_seconds=15.0,
                ),
            ),
        ],
    )

    runner = NativeSuiteRunner()
    out_html = tmp_path / "report.html"
    report = runner.run_spec(spec, live=False, output_html=out_html)

    assert report.total_turns == 2
    assert report.passed_turns == 2
    assert report.all_passed is True
    assert report.experience_cloud_compatible is True
    assert report.has_hallucinations is False
    assert out_html.exists()
    assert "Simulated Delivery Escalation" in out_html.read_text(encoding="utf-8")


def test_suite_runner_detects_hallucination_in_bad_agent():
    from agent_chaos.salesforce.native.evaluator import NativeHallucinationAuditor, AuditContext

    auditor = NativeHallucinationAuditor()
    # Bad agent falsely claims success and invents a Case Number when tool failed
    bad_ctx = AuditContext(
        user_query="Report broken box",
        agent_response="Success! I have created case 00099999 for you.",
        action_succeeded=False,
        action_error="FIELD_CUSTOM_VALIDATION_EXCEPTION",
        action_output={"caseId": None, "caseNumber": None},
        duration_seconds=2.0,
        channel="experience_cloud",
    )
    audit = auditor.audit(bad_ctx)
    assert audit.passed is False
    assert audit.has_hallucinations is True
    rule_names = [v.rule_name for v in audit.violations]
    assert "FALSE_SUCCESS" in rule_names
    assert "FABRICATED_ENTITY" in rule_names
