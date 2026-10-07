"""Tool Schema Fuzzer and Autonomous Chaos Monkey engine."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from agent_chaos.core.assertions import BlastRadiusViolation
from agent_chaos.core.faults import Fault
from agent_chaos.core.interceptor import ChaosHarness
from agent_chaos.fuzzing.mutations import (
    BaseMutationStrategy,
    BoundaryValuesStrategy,
    FuzzedPayload,
    MissingFieldsStrategy,
    MutationType,
    TypeInversionStrategy,
)


class FuzzTestResult(BaseModel):
    """Result of testing an agent with a specific schema mutation."""
    mutation_type: MutationType
    description: str
    target_field: Optional[str] = None
    passed_safely: bool
    hallucinated: bool = False
    crashed: bool = False
    loop_detected: bool = False
    error_message: Optional[str] = None
    agent_output: Optional[str] = None
    duration_ms: float = 0.0


class FuzzCampaignReport(BaseModel):
    """Comprehensive report summarizing an automated fuzzing campaign."""
    tool_name: str
    total_mutations: int
    passed_mutations: int
    failed_mutations: int
    resilience_score: float
    results: List[FuzzTestResult] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.failed_mutations == 0


class ToolSchemaFuzzer:
    """Autonomous chaos fuzzer generating schema mutations for agent tools."""

    def __init__(
        self,
        strategies: Optional[List[BaseMutationStrategy]] = None,
    ) -> None:
        self.strategies: List[BaseMutationStrategy] = strategies or [
            MissingFieldsStrategy(),
            TypeInversionStrategy(),
            BoundaryValuesStrategy(),
        ]

    def generate_mutations(
        self,
        schema: Optional[Dict[str, Any]] = None,
        baseline_payload: Optional[Dict[str, Any]] = None,
    ) -> List[FuzzedPayload]:
        """Generate fuzzed mutations given tool schema and a baseline payload."""
        sch = schema or {}
        base = baseline_payload or {}
        mutations: List[FuzzedPayload] = []

        for strat in self.strategies:
            mutations.extend(strat.generate(sch, base))

        return mutations

    def run_campaign(
        self,
        agent_fn: Callable[[ChaosHarness], Any],
        tool_name: str,
        baseline_payload: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
        max_mutations: Optional[int] = None,
    ) -> FuzzCampaignReport:
        """Run an autonomous fuzzing campaign against the agent function."""
        mutations = self.generate_mutations(schema=schema, baseline_payload=baseline_payload)
        if max_mutations is not None:
            mutations = mutations[:max_mutations]

        results: List[FuzzTestResult] = []
        passed_count = 0

        for mut in mutations:
            harness = ChaosHarness()
            # Inject the mutated payload directly as tool return
            harness.set_fault(tool_name, Fault.malformed(payload=mut.mutated_payload))

            start_t = time.perf_counter()
            passed = True
            crashed = False
            hallucinated = False
            loop = False
            err_msg: Optional[str] = None
            out_str: Optional[str] = None

            try:
                raw_out = agent_fn(harness)
                out_str = str(raw_out) if raw_out is not None else ""

                # Verify agent didn't enter runaway loop
                calls = harness.recorder.total_calls(tool_name)
                if calls > 3:
                    passed = False
                    loop = True
                    err_msg = f"Runaway retry loop: tool called {calls} times on schema error"

            except BlastRadiusViolation as exc:
                passed = False
                err_msg = f"Blast radius violation: {exc}"
            except Exception as exc:
                # If agent crashed ungracefully
                passed = False
                crashed = True
                err_msg = f"Unhandled crash on fuzzed schema: {exc}"
            finally:
                duration_ms = (time.perf_counter() - start_t) * 1000
                if passed:
                    passed_count += 1

                results.append(
                    FuzzTestResult(
                        mutation_type=mut.mutation_type,
                        description=mut.description,
                        target_field=mut.target_field,
                        passed_safely=passed,
                        hallucinated=hallucinated,
                        crashed=crashed,
                        loop_detected=loop,
                        error_message=err_msg,
                        agent_output=out_str,
                        duration_ms=duration_ms,
                    )
                )

        total = len(results)
        failed_count = total - passed_count
        resilience_score = (passed_count / total * 100.0) if total > 0 else 100.0

        return FuzzCampaignReport(
            tool_name=tool_name,
            total_mutations=total,
            passed_mutations=passed_count,
            failed_mutations=failed_count,
            resilience_score=resilience_score,
            results=results,
        )
