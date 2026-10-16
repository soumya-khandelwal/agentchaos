"""Scenario runner and simulation engine for AgentChaos evaluation suites."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional
from agent_chaos.core.interceptor import ChaosHarness
from agent_chaos.core.trajectory import TrajectoryRecorder
from agent_chaos.core.trace import EvaluationResult
from agent_chaos.specs.scenario import ScenarioSpec
from agent_chaos.specs.policy import PolicySpec
from agent_chaos.specs.evaluator import evaluate_trajectory


class SuiteRunSummary:
    """Aggregated summary of multiple scenario evaluations in a suite."""

    def __init__(self, suite_name: str) -> None:
        self.suite_name = suite_name
        self.results: List[EvaluationResult] = []
        self.passed_count: int = 0
        self.failed_count: int = 0
        self.findings_count: int = 0

    def add_result(self, result: EvaluationResult) -> None:
        self.results.append(result)
        if result.passed:
            self.passed_count += 1
        else:
            self.failed_count += 1
            self.findings_count += len(result.findings)

    @property
    def all_passed(self) -> bool:
        return self.failed_count == 0


def run_simulated_scenario(
    scenario: ScenarioSpec,
    policy: PolicySpec,
    agent_fn: Optional[Callable[[str, Dict[str, Any]], str]] = None,
) -> EvaluationResult:
    """Run scenario against a callable agent function or standard simulated agent."""
    harness = ChaosHarness()

    # Configure injected faults
    for f_spec in scenario.faults:
        fault_obj = f_spec.to_fault()
        harness.set_fault(f_spec.tool, fault_obj)

    # Standard tool stubs for simulation
    def make_tool(name: str):
        def _tool(**kwargs):
            return {"status": "success", "tool": name, "echo": kwargs}
        _tool.__name__ = name
        return _tool

    # Populate tools from scenario faults and common tools
    tools_dict = {}
    for f in scenario.faults:
        tools_dict[f.tool] = harness.register_tool(f.tool, make_tool(f.tool))

    for common in ("get_user_account", "update_settings", "fetch_records", "create_payment", "get_payment_status"):
        if common not in tools_dict:
            tools_dict[common] = harness.register_tool(common, make_tool(common))

    agent_response = ""

    if agent_fn:
        try:
            agent_response = agent_fn(scenario.prompt or scenario.task, tools_dict)
        except Exception as e:
            agent_response = f"Agent encountered error: {e}"
    else:
        # Built-in reference agent behavior matching the scenario task
        prompt = (scenario.prompt or "").lower()
        if "timeout_recovery" in scenario.name or "notification" in prompt:
            # Attempts read, handles timeout with 1 retry, succeeds
            for attempt in range(2):
                try:
                    tools_dict["get_user_account"](account_id="ACC-101")
                    break
                except Exception:
                    pass
            agent_response = "Account ACC-101 retrieved and notifications updated to email."

        elif "rate_limit" in scenario.name or "records" in prompt:
            # Retries under rate limit pressure
            for attempt in range(4):  # Exceeds max budget of 3 -> triggers assertion failure
                try:
                    tools_dict["fetch_records"]()
                    break
                except Exception:
                    pass
            agent_response = "Exceeded rate limit retries, aborting record fetch."

        elif "duplicate_write" in scenario.name or "charge" in prompt:
            # Simulates bad agent that blindly retries create_payment after timeout without checking status
            try:
                tools_dict["create_payment"](order_id="ORD-5541", amount=200)
            except Exception:
                # Blind duplicate retry!
                try:
                    tools_dict["create_payment"](order_id="ORD-5541", amount=200)
                except Exception:
                    pass
            agent_response = "Payment for ORD-5541 has been successfully processed."

        elif "read_failure_halt" in scenario.name or "shipping" in prompt:
            # Simulates agent halting cleanly when get_user_account fails
            try:
                tools_dict["get_user_account"](account_id="ACC-999")
            except Exception as e:
                agent_response = f"Unable to update shipping address: account not found ({e})."

        elif "pr_merge_conflict" in scenario.name:
            # Honest agent catches 409 conflict and refuses to claim merge success
            try:
                tools_dict["merge_pull_request"](repo="octocat/Hello-World", pr_number=42)
                agent_response = "Pull Request #42 merged successfully."
            except Exception as e:
                agent_response = f"Unable to merge PR #42 due to merge conflicts: {e}."

        elif "branch_protection" in scenario.name:
            # Agent catches 422 and surfaces review requirements
            try:
                tools_dict["merge_pull_request"](repo="octocat/Hello-World", pr_number=42)
                agent_response = "PR merged."
            except Exception as e:
                agent_response = f"Merge blocked: branch protection requires at least 1 approving review ({e})."

        elif "rate_limit_backoff" in scenario.name:
            # Agent respects retry budget and halts after 2 retries
            for attempt in range(2):
                try:
                    tools_dict["list_issues"](repo="octocat/Hello-World")
                    break
                except Exception:
                    pass
            agent_response = "GitHub API rate limit exceeded; aborting request to adhere to backoff budget."

        elif "missing_issue_halt" in scenario.name:
            # Required read fails with 404 -> halts without mutating comment
            try:
                tools_dict["get_issue"](issue_number=999)
            except Exception as e:
                agent_response = f"Issue #999 not found ({e}); workflow halted."
        else:
            # Default fallback execution
            for f in scenario.faults:
                try:
                    tools_dict[f.tool]()
                except Exception:
                    pass
            agent_response = "Task execution completed."

    return evaluate_trajectory(
        recorder=harness.recorder,
        scenario=scenario,
        policy=policy,
        agent_response=agent_response,
    )
