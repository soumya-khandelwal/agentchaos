"""GitHub Actions CI workflow template generator for AgentChaos."""

from __future__ import annotations

GITHUB_ACTIONS_WORKFLOW_TEMPLATE = """# .github/workflows/agent-chaos-ci.yml
name: AgentChaos Resilience & Hallucination Audit

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  agent-chaos-audit:
    name: GitHub Agent Crash-Test & False-Success Audit
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install agent-chaos pytest

      - name: Run GitHub Agent Chaos Tests
        run: |
          agent-chaos test tests/

      - name: Export JUnit Report
        if: always()
        run: |
          pytest tests/ --junitxml=reports/junit.xml || true

      - name: Upload Test Report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: agent-chaos-report
          path: reports/
"""


def generate_github_ci_workflow() -> str:
    """Return the standard GitHub Actions YAML string."""
    return GITHUB_ACTIONS_WORKFLOW_TEMPLATE
