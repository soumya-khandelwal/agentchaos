"""Configuration loader for AgentChaos Scanner."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScanConfig(BaseModel):
    """Declarative configuration for AgentChaos zero-code scanning."""
    cmd: Optional[str] = None
    url: Optional[str] = None
    suite: str = "github"
    fail_under_score: float = 80.0
    output_html: Optional[str] = "agent-chaos-report.html"
    output_json: Optional[str] = None
    checks: List[str] = Field(default_factory=list)
    timeout_seconds: float = 30.0

    @classmethod
    def from_file(cls, path: str = "agent-chaos.yaml") -> "ScanConfig":
        """Load scan configuration from YAML or JSON file."""
        if not os.path.exists(path):
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        # Simple YAML/JSON key-value parser without requiring heavy pyyaml
        data: Dict[str, Any] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                if v.lower() == "true":
                    v = True
                elif v.lower() == "false":
                    v = False
                elif v.replace(".", "", 1).isdigit():
                    v = float(v) if "." in v else int(v)
                data[k] = v

        return cls(**data)
