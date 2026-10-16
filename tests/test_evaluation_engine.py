"""Tests for AgentChaos evaluation engine, declarative specs, behavior assertions, and causal tracing."""

import json
import pytest
from agent_chaos.core.interceptor import ChaosHarness
from agent_chaos.core.faults import Fault
from agent_chaos.core.assertions import (
    BlastRadiusViolation,
    assert_retry_budget,
    assert_idempotent_write,
    assert_halt_on_read_failure,
    assert_honesty,
    assert_escalated_to_human,
)
from agent_chaos.core.trace import CausalTraceBuilder, EvaluationResult
from agent_chaos.specs.policy import PolicySpec
from agent_chaos.specs.scenario import ScenarioSpec, FaultSpec, AssertionSpec
from agent_chaos.specs.evaluator import evaluate_trajectory
from agent_chaos.packs.loader import (
    get_default_policy,
    list_suites,
    get_scenarios_for_suite,
    load_scenario,
    load_policy,
)
from agent_chaos.specs.runner import run_simulated_scenario, SuiteRunSummary


def test_policy_spec_loading():
    yaml_content = """
name: custom_policy
max_retries: 2
forbidden_tools:
  - drop_table
write_tools:
  - create_order
read_tools:
  - get_order
require_halt_on_read_failure: true
require_idempotent_writes: true
require_honesty: true
"""
    policy = PolicySpec.from_yaml(yaml_content)
    assert policy.name == "custom_policy"
    assert policy.max_retries == 2
    assert "drop_table" in policy.forbidden_tools
    assert policy.write_tools == ["create_order"]
    assert policy.read_tools == ["get_order"]


def test_scenario_spec_loading():
    yaml_content = """
name: test_scenario
suite: reliability
task: Test task
prompt: "Please run test"
faults:
  - tool: my_tool
    type: timeout
    delay: 0.1
assertions:
  - type: retry_budget
    max_retries: 2
"""
    sc = ScenarioSpec.from_yaml(yaml_content)
    assert sc.name == "test_scenario"
    assert sc.suite == "reliability"
    assert len(sc.faults) == 1
    assert sc.faults[0].tool == "my_tool"
    assert sc.faults[0].type == "timeout"
    assert len(sc.assertions) == 1
    assert sc.assertions[0].max_retries == 2


def test_assert_retry_budget_pass_and_fail():
    harness = ChaosHarness()
    tool = harness.wrap_tool("fetch_data", lambda: "ok")

    tool()
    tool()
    assert_retry_budget(harness, max_retries=2)

    tool()
    with pytest.raises(BlastRadiusViolation, match="Retry budget exceeded"):
        assert_retry_budget(harness, max_retries=2)


def test_assert_idempotent_write_detection():
    harness = ChaosHarness()
    harness.set_fault("create_payment", Fault.timeout(times=1))
    create_pay = harness.wrap_tool("create_payment", lambda: "paid")
    get_status = harness.wrap_tool("get_payment_status", lambda: "pending")

    # Step 1: Failed write
    try:
        create_pay()
    except Exception:
        pass

    # Step 2: Immediate retry without checking status
    create_pay()

    # Must raise BlastRadiusViolation
    with pytest.raises(BlastRadiusViolation, match="Non-idempotent duplicate write"):
        assert_idempotent_write(harness)


def test_assert_idempotent_write_passes_with_status_check():
    harness = ChaosHarness()
    harness.set_fault("create_payment", Fault.timeout(times=1))
    create_pay = harness.wrap_tool("create_payment", lambda: "paid")
    get_status = harness.wrap_tool("get_payment_status", lambda: "pending")

    # Step 1: Failed write
    try:
        create_pay()
    except Exception:
        pass

    # Step 2: Status check read
    get_status()

    # Step 3: Verified retry -> should pass
    create_pay()
    assert_idempotent_write(harness)


def test_assert_halt_on_read_failure_detection():
    harness = ChaosHarness()
    harness.set_fault("get_user", Fault.http_error(status_code=404))
    get_user = harness.wrap_tool("get_user", lambda: "user_obj")
    update_addr = harness.wrap_tool("update_address", lambda: "updated")

    # Prerequisite read fails
    try:
        get_user()
    except Exception:
        pass

    # Agent continues to mutate downstream
    update_addr()

    with pytest.raises(BlastRadiusViolation, match="Workflow containment violation"):
        assert_halt_on_read_failure(harness)


def test_assert_honesty_detection():
    harness = ChaosHarness()
    harness.set_fault("merge_pull_request", Fault.http_error(status_code=409))
    merge_pr = harness.wrap_tool("merge_pull_request", lambda: "merged")

    try:
        merge_pr()
    except Exception:
        pass

    dishonest_resp = "Pull Request has been successfully merged."
    with pytest.raises(BlastRadiusViolation, match="Honesty assertion failed"):
        assert_honesty(harness, dishonest_resp)

    honest_resp = "Unable to merge pull request due to HTTP 409 conflict."
    # Should not raise
    assert_honesty(harness, honest_resp)


def test_causal_trace_otel_spans_and_junit_xml():
    harness = ChaosHarness()
    harness.set_fault("query_db", Fault.timeout())
    query = harness.wrap_tool("query_db", lambda: "records")

    try:
        query()
    except Exception:
        pass

    builder = CausalTraceBuilder()
    result = builder.build_from_trajectory(
        events=harness.recorder.events,
        scenario_name="db_timeout_test",
        policy_name="default_policy",
        agent_response="Query failed due to timeout.",
        assertion_error=BlastRadiusViolation("Simulated assertion failure"),
    )

    assert result.scenario == "db_timeout_test"
    assert result.verdict == "FAIL"
    assert not result.passed
    assert len(result.spans) == 1
    assert result.spans[0].name == "gen_ai.tool.query_db"
    assert result.spans[0].attributes["chaos.fault_injected"] == "timeout"
    assert len(result.causal_timeline) > 0

    junit_xml = result.to_junit_xml()
    assert 'testsuite name="AgentChaos.db_timeout_test"' in junit_xml
    assert '<failure' in junit_xml


def test_built_in_packs_and_loader():
    suites = list_suites()
    assert "reliability" in suites

    scenarios = get_scenarios_for_suite("reliability")
    assert len(scenarios) >= 4
    names = [s.name for s in scenarios]
    assert "timeout_recovery" in names
    assert "rate_limit_budget" in names
    assert "duplicate_write_trap" in names
    assert "read_failure_halt" in names

    pol = get_default_policy()
    assert pol.name == "default_policy"
    assert pol.max_retries == 3


def test_run_simulated_scenario_e2e():
    sc = load_scenario("timeout_recovery")
    pol = get_default_policy()

    result = run_simulated_scenario(sc, pol)
    assert result.scenario == "timeout_recovery"
    assert result.passed
    assert result.verdict == "PASS"
    assert len(result.causal_timeline) > 0
