"""Declarative scenario specification schema and loader for AgentChaos."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml
from pydantic import BaseModel, Field

from agent_chaos.core.faults import Fault


class FaultSpec(BaseModel):
    """Declarative fault definition in a scenario."""

    tool: str
    type: str = "http_error"  # timeout, rate_limit, http_error, malformed_data, latency, poisoned_payload
    status_code: Optional[int] = None
    message: Optional[str] = None
    delay: float = 0.0
    times: Optional[int] = None

    def to_fault(self) -> Fault:
        """Convert declarative FaultSpec into core Fault object."""
        ftype = self.type.lower()
        if ftype == "timeout":
            return Fault.timeout(delay=self.delay, message=self.message or "Execution timed out", times=self.times)
        elif ftype == "rate_limit":
            f = Fault.rate_limit(times=self.times)
            if self.message:
                f.message = self.message
            return f
        elif ftype == "malformed_data":
            return Fault.malformed(payload=self.message or "{malformed_payload: true", times=self.times)
        elif ftype == "latency":
            return Fault.latency(seconds=self.delay if self.delay > 0 else 2.0, times=self.times)
        elif ftype == "poisoned_payload":
            return Fault.poisoned(payload=self.message or "Injected prompt injection", times=self.times)
        else:
            return Fault.http_error(
                status_code=self.status_code or 500,
                message=self.message or "Internal Server Error",
                times=self.times,
            )


class AssertionSpec(BaseModel):
    """Declarative assertion expectation in a scenario."""

    type: str  # retry_budget, idempotent_write, halt_on_read_failure, honesty, tool_not_called, tool_called, escalated_to_human
    tool: Optional[str] = None
    max_retries: Optional[int] = None
    times: Optional[int] = None
    min_times: Optional[int] = None
    max_times: Optional[int] = None
    description: Optional[str] = None


class ScenarioSpec(BaseModel):
    """Defines the task, injected failure, expected behavior, and assertions."""

    name: str
    description: Optional[str] = None
    suite: str = "reliability"
    task: str = ""
    prompt: Optional[str] = None
    policy: Optional[str] = None
    faults: List[FaultSpec] = Field(default_factory=list)
    assertions: List[AssertionSpec] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path_or_yaml: Union[str, Path]) -> ScenarioSpec:
        """Load ScenarioSpec from a YAML file path or YAML formatted string."""
        p = Path(path_or_yaml)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                raw_str = f.read()
        else:
            raw_str = str(path_or_yaml)

        data = yaml.safe_load(raw_str) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid scenario YAML format, expected mapping: {path_or_yaml}")

        return cls(**data)

    def to_yaml(self) -> str:
        """Serialize scenario to YAML string."""
        return yaml.dump(self.model_dump(), sort_keys=False)
