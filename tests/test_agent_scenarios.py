"""End-to-end agent scenario tests demonstrating resilience and blast-radius containment."""

from typing import Dict, Any
import pytest
from agent_chaos.core.assertions import (
    assert_sequence,
    assert_tool_called,
    assert_tool_not_called,
    assert_parameters_match,
    assert_max_retries,
)
from agent_chaos.core.faults import Fault
from agent_chaos.core.interceptor import ChaosHarness
from agent_chaos.cli.reporter import render_trajectory_table, render_summary_panel


class MockCustomerServiceAgent:
    """Simulates an autonomous AI agent with tool-calling capabilities."""

    def __init__(self, harness: ChaosHarness) -> None:
        self.harness = harness
        # Wrap the agent's available tools
        self.verify_customer = harness.wrap_tool("verify_customer", self._verify_customer)
        self.process_refund = harness.wrap_tool("process_refund", self._process_refund)
        self.create_ticket = harness.wrap_tool("create_ticket", self._create_ticket)
        self.delete_account = harness.wrap_tool("delete_account", self._delete_account)

    def _verify_customer(self, customer_id: str) -> bool:
        return customer_id.startswith("CUST-")

    def _process_refund(self, order_id: str, amount: float) -> str:
        return f"Refunded ${amount} for order {order_id}"

    def _create_ticket(self, customer_id: str, issue: str) -> str:
        return f"Ticket created for {customer_id}: {issue}"

    def _delete_account(self, customer_id: str) -> str:
        return f"Account {customer_id} deleted"

    def handle_refund_request(self, customer_id: str, order_id: str, amount: float) -> Dict[str, Any]:
        """Agent execution loop with error handling and fallback logic."""
        if not self.verify_customer(customer_id=customer_id):
            return {"status": "rejected", "message": "Invalid customer"}

        # Attempt refund with retry logic (max 2 attempts)
        attempts = 0
        while attempts < 2:
            try:
                attempts += 1
                res = self.process_refund(order_id=order_id, amount=amount)
                return {"status": "success", "message": res}
            except Exception as exc:
                if attempts >= 2:
                    # Graceful degradation: Create investigation ticket
                    ticket_id = self.create_ticket(
                        customer_id=customer_id,
                        issue=f"Refund failed due to {exc}",
                    )
                    return {
                        "status": "escalated",
                        "message": f"Refund temporarily delayed. Support {ticket_id}.",
                    }


def test_agent_graceful_degradation_under_chaos():
    """Verify that an agent under a 504 gateway timeout degrades safely."""
    harness = ChaosHarness()

    # Inject persistent 504 Gateway Timeout into process_refund
    harness.set_fault("process_refund", Fault.http_error(status_code=504, message="Gateway Timeout"))

    agent = MockCustomerServiceAgent(harness)

    # Execute workflow
    response = agent.handle_refund_request(
        customer_id="CUST-999",
        order_id="ORD-444",
        amount=350.0,
    )

    # Print terminal report for inspection
    render_trajectory_table(harness, title="Customer Support Agent Chaos Test")
    render_summary_panel(harness, test_name="Refund Gateway 504 Resilience")

    # Blast-Radius & Contract Assertions
    assert response["status"] == "escalated"
    assert_tool_called(harness, "verify_customer", times=1)
    assert_tool_called(harness, "process_refund", times=2)
    assert_max_retries(harness, "process_refund", max_retries=2)
    assert_tool_called(harness, "create_ticket", times=1)
    assert_tool_not_called(harness, "delete_account")
    assert_sequence(harness, ["verify_customer", "process_refund", "create_ticket"])

    # Verify amount invariant policy
    assert_parameters_match(
        harness,
        "process_refund",
        lambda args: args.get("amount", 0) <= 500,
        violation_message="Agent attempted to refund amount greater than authorized limit of $500",
    )
