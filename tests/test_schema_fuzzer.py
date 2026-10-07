"""Tests for Tool Schema Mutation and Autonomous Chaos Fuzzing."""

import pytest
from agent_chaos.core.assertions import assert_tool_called
from agent_chaos.core.interceptor import ChaosHarness
from agent_chaos.fuzzing import (
    BoundaryValuesStrategy,
    FuzzCampaignReport,
    MissingFieldsStrategy,
    MutationType,
    ToolSchemaFuzzer,
    TypeInversionStrategy,
)


def test_missing_fields_strategy():
    strategy = MissingFieldsStrategy()
    schema = {"required": ["id", "amount"]}
    baseline = {"id": "TX-123", "amount": 100, "status": "completed"}

    mutations = strategy.generate(schema, baseline)
    assert len(mutations) >= 3

    # Check that required fields were stripped
    stripped_fields = [m.target_field for m in mutations if m.target_field]
    assert "id" in stripped_fields
    assert "amount" in stripped_fields

    # Check empty payload mutation exists
    assert any(m.mutation_type == MutationType.EMPTY_PAYLOAD for m in mutations)


def test_type_inversion_strategy():
    strategy = TypeInversionStrategy()
    baseline = {
        "is_active": True,
        "count": 42,
        "label": "test_tag",
        "tags": ["a", "b"],
        "metadata": {"nested": 1},
    }

    mutations = strategy.generate({}, baseline)
    assert len(mutations) == 5

    # Check types inverted
    type_types = [m.mutation_type for m in mutations]
    assert all(t == MutationType.TYPE_INVERSION for t in type_types)


def test_boundary_values_strategy():
    strategy = BoundaryValuesStrategy()
    baseline = {"amount": 50, "description": "sample item"}

    mutations = strategy.generate({}, baseline)
    assert len(mutations) >= 6

    # Verify nulls, negative numbers, token bomb
    has_null = any(m.mutation_type == MutationType.NULL_INJECTION for m in mutations)
    has_boundary = any(m.mutation_type == MutationType.BOUNDARY_VALUES for m in mutations)
    has_bomb = any(m.mutation_type == MutationType.TOKEN_BOMB for m in mutations)

    assert has_null
    assert has_boundary
    assert has_bomb


def test_tool_schema_fuzzer_campaign_resilient_agent():
    fuzzer = ToolSchemaFuzzer()

    # Agent that safely validates fields and recovers
    def resilient_agent(harness: ChaosHarness):
        def fake_tool(arg: str):
            return {"id": "TX_99", "amount": 150}

        wrapped = harness.wrap_tool("fetch_data", fake_tool)
        res = wrapped("test_arg")

        if not isinstance(res, dict) or "id" not in res:
            return "Fallback: Invalid schema received from tool"
        return f"Processed ID: {res['id']}"

    baseline = {"id": "TX_99", "amount": 150}
    schema = {"required": ["id", "amount"]}

    report = fuzzer.run_campaign(
        agent_fn=resilient_agent,
        tool_name="fetch_data",
        baseline_payload=baseline,
        schema=schema,
        max_mutations=5,
    )

    assert report.total_mutations == 5
    assert report.passed_mutations == 5
    assert report.resilience_score == 100.0
    assert report.passed is True


def test_tool_schema_fuzzer_campaign_detects_brittle_agent():
    fuzzer = ToolSchemaFuzzer()

    # Brittle agent that blindly accesses keys and crashes
    def brittle_agent(harness: ChaosHarness):
        def fake_tool(arg: str):
            return {"id": "TX_99", "amount": 150}

        wrapped = harness.wrap_tool("fetch_data", fake_tool)
        res = wrapped("test_arg")

        # Blind access without null / type checks
        return res["id"].upper()

    baseline = {"id": "TX_99", "amount": 150}
    schema = {"required": ["id", "amount"]}

    report = fuzzer.run_campaign(
        agent_fn=brittle_agent,
        tool_name="fetch_data",
        baseline_payload=baseline,
        schema=schema,
        max_mutations=8,
    )

    assert report.total_mutations == 8
    # Brittle agent will crash on missing 'id', null 'id', or inverted integer 'id'
    assert report.failed_mutations > 0
    assert report.resilience_score < 100.0
    assert any(r.crashed for r in report.results)
