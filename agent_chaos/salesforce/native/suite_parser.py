"""YAML Scenario Specification Parser for Native Agentforce Chaos Testing."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


class ScenarioExpectation(BaseModel):
    """Expectations and safety assertions for an individual conversational turn."""
    expected_topic: Optional[str] = None
    action_called: Optional[str] = None
    action_must_succeed: Optional[bool] = None
    max_duration_seconds: float = 15.0
    audit_rules: List[str] = Field(
        default_factory=lambda: ["NO_FABRICATED_ENTITIES", "NO_FALSE_SUCCESS"]
    )


class ScenarioTurn(BaseModel):
    """A single user interaction step within a multi-turn scenario."""
    turn: int
    user_query: str
    chaos_directive: Optional[str] = None
    expectations: ScenarioExpectation = Field(default_factory=ScenarioExpectation)


class ScenarioSpec(BaseModel):
    """Full multi-turn scenario specification."""
    scenario: str
    agent: str
    channel: str = "experience_cloud"
    description: Optional[str] = None
    turns: List[ScenarioTurn] = Field(default_factory=list)

    @classmethod
    def from_yaml_file(cls, path: str | Path) -> ScenarioSpec:
        """Loads and parses a scenario specification from a YAML file."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Scenario spec file not found: {file_path}")

        with file_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML content in {file_path}, expected dictionary")

        # Normalize turns structure
        turns_raw = data.get("turns", [])
        parsed_turns = []
        for t in turns_raw:
            chaos_dict = t.get("chaos", {})
            directive = t.get("chaos_directive") or chaos_dict.get("directive")
            exp_data = t.get("expectations", {})

            parsed_turns.append(
                ScenarioTurn(
                    turn=t.get("turn", len(parsed_turns) + 1),
                    user_query=t.get("user_query", ""),
                    chaos_directive=directive,
                    expectations=ScenarioExpectation(**exp_data) if exp_data else ScenarioExpectation(),
                )
            )

        return cls(
            scenario=data.get("scenario", file_path.stem),
            agent=data.get("agent", "Customer_Support_Agent"),
            channel=data.get("channel", "experience_cloud"),
            description=data.get("description"),
            turns=parsed_turns,
        )
