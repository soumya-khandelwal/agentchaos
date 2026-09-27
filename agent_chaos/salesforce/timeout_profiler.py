"""Timeout and latency budget profiler to diagnose Experience Cloud vs. Agentforce Builder drop-offs."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class LatencyTrial(BaseModel):
    """Result of a single trial run at a specific injected delay."""
    injected_delay_seconds: float
    total_duration_seconds: float
    passed_experience_cloud_sla: bool
    passed_builder_sla: bool
    status: str
    error: Optional[str] = None


class TimeoutProfileReport(BaseModel):
    """Diagnostic report pinpointing when Experience Cloud drops the agent connection."""
    experience_cloud_sla_seconds: float
    builder_sla_seconds: float
    max_safe_tool_delay_seconds: float
    dropoff_cliff_seconds: Optional[float] = None
    trials: List[LatencyTrial] = Field(default_factory=list)
    diagnosis: str = ""


class TimeoutProfiler:
    """Simulates increasing downstream tool delays to determine the Experience Cloud failure cliff."""

    def __init__(
        self,
        experience_cloud_sla: float = 15.0,
        builder_sla: float = 45.0,
    ) -> None:
        self.experience_cloud_sla = experience_cloud_sla
        self.builder_sla = builder_sla

    def profile_action(
        self,
        runner_fn: Callable[[float], Any],
        delay_steps: Optional[List[float]] = None,
    ) -> TimeoutProfileReport:
        """Run the agent action across incremental delays to locate the exact timeout drop cliff."""
        steps = delay_steps if delay_steps is not None else [0.0, 5.0, 10.0, 14.0, 18.0, 22.0]
        trials: List[LatencyTrial] = []

        max_safe_delay = 0.0
        cliff_delay: Optional[float] = None

        for delay in steps:
            start_t = time.perf_counter()
            err_msg: Optional[str] = None
            status = "SUCCESS"

            try:
                runner_fn(delay)
            except Exception as exc:
                err_msg = str(exc)
                status = "FAILED"

            duration = time.perf_counter() - start_t
            passed_exp = (duration <= self.experience_cloud_sla) and (err_msg is None)
            passed_bld = (duration <= self.builder_sla) and (err_msg is None)

            if passed_exp:
                max_safe_delay = max(max_safe_delay, delay)
            elif cliff_delay is None:
                cliff_delay = delay

            trials.append(
                LatencyTrial(
                    injected_delay_seconds=delay,
                    total_duration_seconds=duration,
                    passed_experience_cloud_sla=passed_exp,
                    passed_builder_sla=passed_bld,
                    status=status,
                    error=err_msg,
                )
            )

        # Generate diagnosis
        if cliff_delay is not None:
            diagnosis = (
                f"⚠️ Discrepancy Found! Agent succeeds in Builder but drops on Experience Cloud "
                f"when tool delay reaches ~{cliff_delay:.1f}s. "
                f"Total turn duration exceeds Experience Cloud's {self.experience_cloud_sla:.1f}s client SLA."
            )
        else:
            diagnosis = "✅ All evaluated latency steps completed within Experience Cloud SLA budget."

        return TimeoutProfileReport(
            experience_cloud_sla_seconds=self.experience_cloud_sla,
            builder_sla_seconds=self.builder_sla,
            max_safe_tool_delay_seconds=max_safe_delay,
            dropoff_cliff_seconds=cliff_delay,
            trials=trials,
            diagnosis=diagnosis,
        )
