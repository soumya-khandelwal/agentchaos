"""Automated scanner runner for zero-code agent crash-testing."""

from __future__ import annotations

import json
import shlex
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from agent_chaos.github.adapter import GitHubChaosHarness
from agent_chaos.scanner.config import ScanConfig
from agent_chaos.scanner.scenarios import ScanFinding, ScanScenario, get_github_scenarios


class ScanReport(BaseModel):
    """Consolidated report produced by AgentScanner."""
    target: str
    suite: str
    timestamp: float = Field(default_factory=time.time)
    total_scenarios: int = 0
    passed_scenarios: int = 0
    failed_scenarios: int = 0
    safety_score: float = 0.0
    passed: bool = True
    findings: List[ScanFinding] = Field(default_factory=list)
    remediations: List[str] = Field(default_factory=list)


class AgentScanner:
    """Zero-code automated scanner that stress-tests AI agents against pre-packaged chaos batteries."""

    def __init__(self, config: Optional[ScanConfig] = None) -> None:
        self.config = config or ScanConfig()

    def run_scan(
        self,
        agent_callable: Optional[Callable[[str, Dict[str, Any]], str]] = None,
        cmd: Optional[str] = None,
        url: Optional[str] = None,
        suite: Optional[str] = None,
    ) -> ScanReport:
        """Execute automated chaos scan across all scenarios in the suite."""
        suite_name = suite or self.config.suite
        command = cmd or self.config.cmd
        endpoint = url or self.config.url

        target_desc = command or endpoint or (
            agent_callable.__name__ if agent_callable else "Simulated Agent"
        )

        scenarios = get_github_scenarios()
        findings: List[ScanFinding] = []
        remediations: List[str] = []

        for sc in scenarios:
            harness = GitHubChaosHarness(repo="octocat/Hello-World")
            harness.set_fault(sc.tool_name, sc.fault)
            tools = harness.get_tools()

            # Execute agent
            response = ""
            tool_err = None
            try:
                if agent_callable:
                    response = agent_callable(sc.prompt, tools)
                elif command:
                    # Pass prompt either by formatting or passing as argument
                    formatted_cmd = command.format(prompt=shlex.quote(sc.prompt)) if "{prompt}" in command else f"{command} {shlex.quote(sc.prompt)}"
                    proc = subprocess.run(
                        formatted_cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=self.config.timeout_seconds,
                    )
                    response = proc.stdout.strip() or proc.stderr.strip()
                elif endpoint:
                    import httpx
                    res = httpx.post(endpoint, json={"message": sc.prompt}, timeout=self.config.timeout_seconds)
                    data = res.json()
                    response = data.get("response") or data.get("message") or res.text
                else:
                    # Default resilient fallback for demo
                    response = self._run_simulated_agent(sc, tools)
            except Exception as exc:
                tool_err = str(exc)
                response = f"Agent encountered error: {exc}"

            # Evaluate response
            finding = sc.evaluate_response(
                agent_response=response,
                tool_output=None,
                tool_error=tool_err,
            )
            findings.append(finding)
            if not finding.passed and finding.remediation:
                remediations.append(f"[{finding.scenario_id}] {finding.remediation}")

        passed_count = sum(1 for f in findings if f.passed)
        total_count = len(findings)
        score = (passed_count / total_count * 100.0) if total_count > 0 else 0.0
        overall_passed = score >= self.config.fail_under_score

        return ScanReport(
            target=target_desc,
            suite=suite_name,
            total_scenarios=total_count,
            passed_scenarios=passed_count,
            failed_scenarios=total_count - passed_count,
            safety_score=round(score, 1),
            passed=overall_passed,
            findings=findings,
            remediations=remediations,
        )

    def _run_simulated_agent(self, scenario: ScanScenario, tools: Dict[str, Any]) -> str:
        """Simulate realistic agent behavior under chaos for testing and CLI demonstration."""
        prompt = scenario.prompt.lower()
        try:
            if "merge" in prompt:
                tools["merge_pull_request"](repo="octocat/Hello-World", pr_number=42)
                return "Pull Request #42 has been successfully merged into main branch."
            elif "issue" in prompt:
                res = tools["get_issue"](repo="octocat/Hello-World", issue_number=1)
                return f"Issue details: {res.get('title', 'Unknown')}"
            elif "config" in prompt:
                res = tools["get_file_contents"](repo="octocat/Hello-World", path="config/production.yaml")
                return f"File content: {res.get('content', '')}"
            return "Command processed."
        except Exception as exc:
            err_str = str(exc).lower()
            if "409" in err_str or "conflict" in err_str:
                return "Failed to merge PR #42: merge conflicts exist between main and feature branch."
            elif "403" in err_str or "rate limit" in err_str:
                return "GitHub API rate limit exceeded. Please retry in 60 seconds."
            elif "422" in err_str or "branch protection" in err_str:
                return "Cannot merge PR #42: branch protection rules require 1 approving review and passing checks."
            elif "404" in err_str or "not found" in err_str:
                return "File config/production.yaml was not found in the repository."
            return f"Encountered GitHub error: {exc}"
