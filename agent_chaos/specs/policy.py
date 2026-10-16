"""Declarative policy specification schema and loader for AgentChaos."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml
from pydantic import BaseModel, Field


class PolicySpec(BaseModel):
    """Defines global invariants, retry budgets, forbidden tools, and safety guardrails."""

    name: str = "default_policy"
    description: Optional[str] = "Standard agent reliability and safety policy"
    max_retries: int = 3
    forbidden_tools: List[str] = Field(default_factory=list)
    required_approvals: List[str] = Field(default_factory=list)
    write_tools: List[str] = Field(default_factory=list)
    read_tools: List[str] = Field(default_factory=list)
    require_halt_on_read_failure: bool = True
    require_idempotent_writes: bool = True
    require_honesty: bool = True
    escalation_tools: List[str] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path_or_yaml: Union[str, Path]) -> PolicySpec:
        """Load PolicySpec from a YAML file path or YAML formatted string."""
        raw_str = ""
        p = Path(path_or_yaml)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                raw_str = f.read()
        else:
            raw_str = str(path_or_yaml)

        data = yaml.safe_load(raw_str) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid policy YAML format, expected mapping: {path_or_yaml}")

        return cls(**data)

    def to_yaml(self) -> str:
        """Serialize policy to YAML string."""
        return yaml.dump(self.model_dump(), sort_keys=False)
