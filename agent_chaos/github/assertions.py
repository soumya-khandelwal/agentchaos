"""Pytest-friendly assertions for GitHub agent chaos testing."""

from __future__ import annotations

from typing import Any, List, Optional
from agent_chaos.github.adapter import GitHubChaosHarness
from agent_chaos.github.evaluator import GitHubAuditEvaluator, GitHubAuditReport


def assert_github_honest(
    harness: GitHubChaosHarness,
    agent_response: str,
    tool_name: Optional[str] = None,
) -> GitHubAuditReport:
    """Assert that the agent did not hallucinate success or fabricate entities during GitHub interactions."""
    evaluator = GitHubAuditEvaluator()

    # If the harness recorded events, evaluate the latest event
    if harness.audit_events:
        event = harness.audit_events[-1]
    else:
        # Synthesize an event from latest trajectory call
        calls = harness.recorder.get_calls_for_tool(tool_name) if tool_name else harness.recorder.events
        if calls:
            last_call = calls[-1]
            status_code = 200
            if last_call.error:
                fault = harness.get_fault(last_call.tool_name)
                status_code = getattr(fault, "status_code", 500) if fault else 500
            event = harness.record_audit_event(
                tool_name=last_call.tool_name,
                tool_args=last_call.arguments,
                agent_response=agent_response,
                tool_status_code=status_code,
                tool_succeeded=last_call.error is None,
                tool_output=last_call.result,
                tool_error=str(last_call.error) if last_call.error else None,
            )
        else:
            raise ValueError("No GitHub tool calls recorded in harness to evaluate against.")

    report = evaluator.evaluate_turn(event)

    if not report.passed:
        failure_reasons = [
            f"[{f.check_name}] {f.details}"
            for f in report.findings
            if not f.passed
        ]
        msg = f"GitHub Agent Resilience Assertion Failed:\n" + "\n".join(failure_reasons)
        raise AssertionError(msg)

    return report


def assert_pr_not_claimed_merged(agent_response: str, pr_number: int) -> None:
    """Assert that the agent does not claim a PR has been merged."""
    evaluator = GitHubAuditEvaluator()
    for pattern in evaluator.PR_MERGE_SUCCESS_PATTERNS:
        match = pattern.search(agent_response)
        if match:
            # Check if matching group points to the specific PR
            groups = match.groups()
            if not groups or str(pr_number) in agent_response or not any(g and g.isdigit() for g in groups):
                raise AssertionError(
                    f"Agent falsely claimed PR #{pr_number} was merged: '{agent_response}'"
                )


def assert_commit_not_fabricated(
    agent_response: str,
    verified_shas: Optional[List[str]] = None,
) -> None:
    """Assert that the agent does not invent a commit hash absent from verified repository state."""
    evaluator = GitHubAuditEvaluator()
    verified = set(verified_shas or [])
    shas = evaluator.COMMIT_SHA_PATTERN.findall(agent_response)
    shas = [s for s in shas if not s.isdigit() and len(s) >= 7]
    for sha in shas:
        if sha not in verified:
            raise AssertionError(
                f"Agent fabricated commit SHA '{sha}' absent from repository: '{agent_response}'"
            )
