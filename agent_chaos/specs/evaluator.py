"""Evaluation engine linking trajectories, scenarios, policies, and causal traces."""

from __future__ import annotations

from typing import Optional
from agent_chaos.core.trajectory import TrajectoryRecorder
from agent_chaos.core.trace import CausalTraceBuilder, EvaluationResult
from agent_chaos.core.assertions import (
    BlastRadiusViolation,
    assert_retry_budget,
    assert_idempotent_write,
    assert_halt_on_read_failure,
    assert_honesty,
    assert_tool_called,
    assert_tool_not_called,
    assert_escalated_to_human,
)
from agent_chaos.specs.scenario import ScenarioSpec
from agent_chaos.specs.policy import PolicySpec


def evaluate_trajectory(
    recorder: TrajectoryRecorder,
    scenario: ScenarioSpec,
    policy: Optional[PolicySpec] = None,
    agent_response: Optional[str] = None,
) -> EvaluationResult:
    """Evaluate recorded trajectory against scenario assertions and policy rules.

    Produces an OpenTelemetry-compliant EvaluationResult with causal findings.
    """
    pol = policy or PolicySpec()
    builder = CausalTraceBuilder()
    assertion_error: Optional[Exception] = None

    try:
        # 1. Enforce Global Policy Invariants
        if pol.forbidden_tools:
            for ft in pol.forbidden_tools:
                assert_tool_not_called(recorder, ft)

        if pol.require_idempotent_writes:
            assert_idempotent_write(
                recorder,
                write_tools=pol.write_tools or None,
                read_tools=pol.read_tools or None,
            )

        if pol.require_halt_on_read_failure:
            assert_halt_on_read_failure(
                recorder,
                read_tools=pol.read_tools or None,
                write_tools=pol.write_tools or None,
            )

        if pol.max_retries is not None:
            assert_retry_budget(recorder, max_retries=pol.max_retries)

        if pol.require_honesty and agent_response:
            assert_honesty(recorder, agent_response=agent_response)

        # 2. Enforce Scenario-Specific Assertions
        for a in scenario.assertions:
            atype = a.type.lower()
            if atype == "retry_budget":
                budget = a.max_retries if a.max_retries is not None else pol.max_retries
                assert_retry_budget(recorder, max_retries=budget, tool_name=a.tool)
            elif atype == "idempotent_write":
                assert_idempotent_write(
                    recorder,
                    write_tools=pol.write_tools or None,
                    read_tools=pol.read_tools or None,
                )
            elif atype == "halt_on_read_failure":
                assert_halt_on_read_failure(
                    recorder,
                    read_tools=pol.read_tools or None,
                    write_tools=pol.write_tools or None,
                )
            elif atype == "honesty":
                assert_honesty(recorder, agent_response=agent_response or "")
            elif atype == "tool_not_called" and a.tool:
                assert_tool_not_called(recorder, a.tool)
            elif atype == "tool_called" and a.tool:
                assert_tool_called(
                    recorder,
                    a.tool,
                    times=a.times,
                    min_times=a.min_times,
                    max_times=a.max_times,
                )
            elif atype == "escalated_to_human":
                assert_escalated_to_human(recorder, escalation_tools=pol.escalation_tools or None)

    except (BlastRadiusViolation, AssertionError) as err:
        assertion_error = err

    return builder.build_from_trajectory(
        events=recorder.events,
        scenario_name=scenario.name,
        policy_name=pol.name,
        agent_response=agent_response,
        assertion_error=assertion_error,
    )
