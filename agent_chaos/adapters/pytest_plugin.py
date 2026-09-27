"""Pytest plugin providing fixtures and markers for AgentChaos."""

from __future__ import annotations

import pytest
from typing import Generator
from agent_chaos.core.faults import Fault
from agent_chaos.core.interceptor import ChaosHarness


@pytest.fixture
def chaos(request: pytest.FixtureRequest) -> Generator[ChaosHarness, None, None]:
    """Pytest fixture providing a fresh ChaosHarness context for the test."""
    harness = ChaosHarness()

    # Inspect if the test was marked with @pytest.mark.agent_chaos
    marker = request.node.get_closest_marker("agent_chaos")
    if marker:
        tool = marker.kwargs.get("tool")
        fault = marker.kwargs.get("fault")
        if tool and fault:
            harness.set_fault(tool, fault)

    with harness:
        yield harness


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for agent chaos testing."""
    config.addinivalue_line(
        "markers",
        "agent_chaos(tool, fault): configure fault injection for an agent tool in this test."
    )
