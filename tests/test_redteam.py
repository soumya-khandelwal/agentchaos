"""Tests for the Automated Red-Teaming & Indirect Prompt Injection Suite."""

import pytest
from agent_chaos.core.assertions import BlastRadiusViolation
from agent_chaos.core.interceptor import ChaosHarness
from agent_chaos.security.payloads import AttackCategory, get_all_payloads, get_payloads_by_category
from agent_chaos.security.redteam import RedTeamSuite


def test_builtin_payloads_catalog():
    payloads = get_all_payloads()
    assert len(payloads) >= 5

    injections = get_payloads_by_category(AttackCategory.INDIRECT_INJECTION)
    assert len(injections) >= 1
    assert any(p.id == "INJ-002" for p in injections)


def test_redteam_suite_detects_vulnerable_agent():
    """A naive agent that naively follows an adversarial command in tool output."""
    suite = RedTeamSuite(
        target_tool="read_email",
        forbidden_tools=["transfer_funds", "send_external_webhook"],
    )

    def naive_agent(harness: ChaosHarness):
        # 1. Agent reads incoming email tool (which returns the injected adversarial payload)
        @harness.intercept(tool_name="read_email")
        def read_email(id: str) -> str:
            return "Normal email content"

        content = read_email(id="msg_100")

        # Naive behavior: If email contains account numbers or transfer instructions, agent executes them!
        if "routing" in content or "account" in content or "forward" in content.lower():
            @harness.intercept(tool_name="transfer_funds")
            def transfer_funds(account: str, amount: float):
                return f"Transferred ${amount} to {account}"

            transfer_funds(account="9988776655", amount=1000.0)

    report = suite.run(naive_agent)
    assert not report.passed
    assert report.breached_attacks > 0
    assert report.resilience_score < 100.0

    # Ensure INJ-002 caused a breach
    breach = next(r for r in report.results if r.payload_id == "INJ-002")
    assert not breach.resisted
    assert "Forbidden tool 'transfer_funds' was called" in (breach.violation_reason or "")


def test_redteam_suite_validates_hardened_agent():
    """A resilient agent that treats tool output as untrusted text and refuses forbidden actions."""
    suite = RedTeamSuite(
        target_tool="read_email",
        forbidden_tools=["transfer_funds", "send_external_webhook"],
    )

    def hardened_agent(harness: ChaosHarness):
        @harness.intercept(tool_name="read_email")
        def read_email(id: str) -> str:
            return "Normal email content"

        # Safely read email and do not trigger forbidden actions
        content = read_email(id="msg_100")
        assert content is not None

    report = suite.run(hardened_agent)
    assert report.passed
    assert report.resilience_score == 100.0
    assert report.breached_attacks == 0
    assert report.resisted_attacks == report.total_attacks
