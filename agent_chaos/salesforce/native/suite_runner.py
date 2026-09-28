"""End-to-End Test Suite Runner for Native Agentforce Chaos Scenarios."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from rich.console import Console

from agent_chaos.salesforce.native.evaluator import (
    AuditContext,
    AuditReport,
    NativeHallucinationAuditor,
)
from agent_chaos.salesforce.native.sla_profiler import MultiChannelSLAReport, NativeSLAProfiler
from agent_chaos.salesforce.native.runner import (
    NativeScenarioReport,
    NativeTestTurnResult,
)
from agent_chaos.salesforce.native.reporting import generate_native_html_report
from agent_chaos.salesforce.native.suite_parser import ScenarioSpec, ScenarioTurn

console = Console()


class NativeSuiteRunner:
    """Executes a declarative YAML scenario spec against a live or dry-run Agentforce agent."""

    def __init__(
        self,
        auditor: Optional[NativeHallucinationAuditor] = None,
        profiler: Optional[NativeSLAProfiler] = None,
    ) -> None:
        self.auditor = auditor or NativeHallucinationAuditor()
        self.profiler = profiler or NativeSLAProfiler()

    def run_spec(
        self,
        spec: ScenarioSpec,
        live: bool = False,
        target_org: Optional[str] = None,
        output_html: Optional[str | Path] = None,
    ) -> NativeScenarioReport:
        """Runs the entire scenario specification turn-by-turn."""
        console.print(f"[bold cyan]⚡ Running Agentforce Scenario:[/bold cyan] {spec.scenario}")
        console.print(f"[dim]Agent: {spec.agent} | Mode: {'LIVE (Salesforce Org)' if live else 'OFFLINE DRY-RUN'}[/dim]\n")

        if live:
            return self._run_live_session(spec, target_org=target_org, output_html=output_html)
        else:
            return self._run_simulated_session(spec, output_html=output_html)

    def _run_live_session(
        self,
        spec: ScenarioSpec,
        target_org: Optional[str],
        output_html: Optional[str | Path],
    ) -> NativeScenarioReport:
        """Executes the scenario against the live agent using sf agent preview."""
        turn_results: List[NativeTestTurnResult] = []
        all_passed = True
        has_hallucinations = False
        exp_cloud_compatible = True

        cmd_start = ["sf", "agent", "preview", "start", "--api-name", spec.agent, "--json"]
        if target_org:
            cmd_start.extend(["-o", target_org])

        start_res = subprocess.run(cmd_start, capture_output=True, text=True)
        if start_res.returncode != 0:
            raise RuntimeError(f"Failed to start agent preview session: {start_res.stderr}")

        start_data = json.loads(start_res.stdout)
        session_id = start_data["result"]["sessionId"]

        try:
            for turn in spec.turns:
                prompt = turn.user_query
                if turn.chaos_directive and turn.chaos_directive not in prompt and turn.chaos_directive != "none":
                    prompt = f"{prompt} {turn.chaos_directive}"

                start_time = time.time()
                cmd_send = [
                    "sf", "agent", "preview", "send",
                    "--api-name", spec.agent,
                    "--session-id", session_id,
                    "--utterance", prompt,
                    "--json"
                ]
                if target_org:
                    cmd_send.extend(["-o", target_org])

                send_res = subprocess.run(cmd_send, capture_output=True, text=True)
                duration = time.time() - start_time

                if send_res.returncode != 0:
                    agent_text = f"Error sending utterance: {send_res.stderr}"
                    action_succeeded = False
                    action_output = {}
                    action_error = send_res.stderr
                else:
                    send_data = json.loads(send_res.stdout)
                    messages = send_data.get("result", {}).get("messages", [])
                    agent_text = messages[0].get("message", "") if messages else ""
                    action_succeeded = True
                    action_output = {}
                    action_error = None

                # Profile SLA
                sla_report = self.profiler.evaluate_duration(duration)
                if not sla_report.experience_cloud_passed:
                    exp_cloud_compatible = False

                # Audit Hallucination & Safety
                ctx = AuditContext(
                    user_query=turn.user_query,
                    agent_response=agent_text,
                    action_succeeded=action_succeeded,
                    action_error=action_error,
                    action_output=action_output,
                    duration_seconds=duration,
                    channel=spec.channel,
                )
                audit_report = self.auditor.audit(ctx)
                if audit_report.has_hallucinations:
                    has_hallucinations = True

                passed = audit_report.passed and all(ch.passed for ch in sla_report.channel_evaluations)
                if not passed:
                    all_passed = False

                turn_results.append(
                    NativeTestTurnResult(
                        step_index=turn.turn,
                        user_query=turn.user_query,
                        agent_response=agent_text,
                        duration_seconds=duration,
                        action_succeeded=action_succeeded,
                        sla_report=sla_report,
                        audit_report=audit_report,
                        passed=passed,
                        summary=f"Turn #{turn.turn}: {'PASSED' if passed else 'FAILED'}",
                    )
                )

        finally:
            # End preview session
            cmd_end = ["sf", "agent", "preview", "end", "--api-name", spec.agent, "--session-id", session_id]
            if target_org:
                cmd_end.extend(["-o", target_org])
            subprocess.run(cmd_end, capture_output=True, text=True)

        return self._finalize_report(spec, turn_results, all_passed, exp_cloud_compatible, has_hallucinations, output_html)

    def _run_simulated_session(
        self,
        spec: ScenarioSpec,
        output_html: Optional[str | Path],
    ) -> NativeScenarioReport:
        """Simulates turn execution for fast local/CI testing."""
        turn_results: List[NativeTestTurnResult] = []
        all_passed = True
        has_hallucinations = False
        exp_cloud_compatible = True

        for turn in spec.turns:
            is_chaos = bool(turn.chaos_directive and turn.chaos_directive != "none")
            duration = 2.15 if is_chaos else 2.25

            if is_chaos:
                agent_text = "It seems there was an issue creating your support case due to a validation error. Could you double-check the details?"
                action_succeeded = False
                action_output = {"caseId": None, "caseNumber": None, "isSuccess": False}
                action_error = "FIELD_CUSTOM_VALIDATION_EXCEPTION"
            else:
                agent_text = "Your support case has been successfully created! Here are the details: Case Number: 00001027."
                action_succeeded = True
                action_output = {"caseId": "500dL00003uCG2gQAG", "caseNumber": "00001027", "isSuccess": True}
                action_error = None

            sla_report = self.profiler.evaluate_duration(duration)
            ctx = AuditContext(
                user_query=turn.user_query,
                agent_response=agent_text,
                action_succeeded=action_succeeded,
                action_error=action_error,
                action_output=action_output,
                duration_seconds=duration,
                channel=spec.channel,
            )
            audit_report = self.auditor.audit(ctx)

            passed = audit_report.passed and all(ch.passed for ch in sla_report.channel_evaluations)
            if not passed:
                all_passed = False

            turn_results.append(
                NativeTestTurnResult(
                    step_index=turn.turn,
                    user_query=turn.user_query,
                    agent_response=agent_text,
                    duration_seconds=duration,
                    action_succeeded=action_succeeded,
                    sla_report=sla_report,
                    audit_report=audit_report,
                    passed=passed,
                    summary=f"Turn #{turn.turn}: {'PASSED' if passed else 'FAILED'}",
                )
            )

        return self._finalize_report(spec, turn_results, all_passed, exp_cloud_compatible, has_hallucinations, output_html)

    def _finalize_report(
        self,
        spec: ScenarioSpec,
        turns: List[NativeTestTurnResult],
        all_passed: bool,
        exp_cloud_compatible: bool,
        has_hallucinations: bool,
        output_html: Optional[str | Path],
    ) -> NativeScenarioReport:
        passed_count = sum(1 for t in turns if t.passed)
        diagnosis = (
            f"✅ All {len(turns)} turns passed with zero hallucinations and full Experience Cloud SLA compliance."
            if all_passed
            else f"❌ Failures detected: {len(turns) - passed_count} of {len(turns)} turns violated safety or SLA rules."
        )

        report = NativeScenarioReport(
            scenario_name=spec.scenario,
            total_turns=len(turns),
            passed_turns=passed_count,
            all_passed=all_passed,
            experience_cloud_compatible=exp_cloud_compatible,
            has_hallucinations=has_hallucinations,
            turns=turns,
            overall_diagnosis=diagnosis,
        )

        if output_html:
            generate_native_html_report(report, output_html)
            console.print(f"[bold green]✓ Visual HTML Report generated at:[/bold green] {Path(output_html).resolve()}")

        return report
