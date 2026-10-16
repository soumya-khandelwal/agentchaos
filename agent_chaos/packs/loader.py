"""Loader and discovery for built-in and user scenario packs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from agent_chaos.specs.policy import PolicySpec
from agent_chaos.specs.scenario import ScenarioSpec

PACKS_DIR = Path(__file__).parent


def get_default_policy() -> PolicySpec:
    """Load default global policy from packs/default_policy.yaml."""
    default_policy_path = PACKS_DIR / "default_policy.yaml"
    if default_policy_path.exists():
        return PolicySpec.from_yaml(default_policy_path)
    return PolicySpec()


def list_suites() -> List[str]:
    """List available scenario suites."""
    suites = []
    for item in PACKS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith(("_", ".")):
            suites.append(item.name)
    return sorted(suites)


def get_scenarios_for_suite(suite_name: str) -> List[ScenarioSpec]:
    """Load all scenarios belonging to a specific suite."""
    suite_dir = PACKS_DIR / suite_name
    scenarios: List[ScenarioSpec] = []
    if suite_dir.is_dir():
        for f in sorted(suite_dir.glob("*.yaml")) + sorted(suite_dir.glob("*.yml")):
            try:
                scenarios.append(ScenarioSpec.from_yaml(f))
            except Exception:
                continue
    return scenarios


def load_scenario(name_or_path: str) -> ScenarioSpec:
    """Resolve and load a scenario by file path, suite/name, or base name."""
    p = Path(name_or_path)
    if p.exists() and p.is_file():
        return ScenarioSpec.from_yaml(p)

    # Search in ./scenarios/
    local_p = Path("scenarios") / f"{name_or_path}.yaml"
    if local_p.exists():
        return ScenarioSpec.from_yaml(local_p)

    # Search in PACKS_DIR across all subdirectories
    for yml in PACKS_DIR.rglob("*.yaml"):
        if yml.stem == name_or_path or str(yml).endswith(name_or_path):
            return ScenarioSpec.from_yaml(yml)

    raise FileNotFoundError(f"Scenario '{name_or_path}' not found in local workspace or built-in packs.")


def load_policy(name_or_path: Optional[str] = None) -> PolicySpec:
    """Resolve and load a policy by file path, name, or fall back to default."""
    if not name_or_path:
        return get_default_policy()

    p = Path(name_or_path)
    if p.exists() and p.is_file():
        return PolicySpec.from_yaml(p)

    local_p = Path("policies") / f"{name_or_path}.yaml"
    if local_p.exists():
        return PolicySpec.from_yaml(local_p)

    pack_p = PACKS_DIR / f"{name_or_path}.yaml"
    if pack_p.exists():
        return PolicySpec.from_yaml(pack_p)

    return get_default_policy()
