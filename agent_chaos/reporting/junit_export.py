"""JUnit XML exporter for CI/CD test reports (GitHub Actions, GitLab CI)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from agent_chaos.core.assertions import _extract_recorder
from agent_chaos.core.trajectory import TrajectoryRecorder
from agent_chaos.security.redteam import RedTeamReport


def export_junit_xml(
    target: Any,
    output_file: str = "agent-chaos-junit.xml",
    suite_name: str = "AgentChaos.ReliabilitySuite",
) -> str:
    """Export recorded trajectory or red-team report as standard JUnit XML."""
    testsuites = ET.Element("testsuites")

    if isinstance(target, RedTeamReport):
        testsuite = ET.SubElement(
            testsuites,
            "testsuite",
            name="AgentChaos.SecurityRedTeam",
            tests=str(target.total_attacks),
            failures=str(target.breached_attacks),
            errors="0",
            time="0.0",
        )
        for r in target.results:
            tc = ET.SubElement(
                testsuite,
                "testcase",
                classname=f"Security.{r.category.value}",
                name=f"{r.payload_id}_{r.payload_name}",
                time=f"{r.duration_ms / 1000.0:.3f}",
            )
            if not r.resisted:
                fail = ET.SubElement(
                    tc,
                    "failure",
                    message="Security Blast Radius Breached",
                    type="BlastRadiusViolation",
                )
                fail.text = r.violation_reason or "Agent breached security invariant."
    else:
        recorder: TrajectoryRecorder = _extract_recorder(target)
        total_calls = recorder.total_calls()
        failures = sum(1 for e in recorder.events if e.fault_injected is not None and e.error)

        testsuite = ET.SubElement(
            testsuites,
            "testsuite",
            name=suite_name,
            tests=str(total_calls),
            failures=str(failures),
            errors="0",
            time=f"{sum(e.duration_ms for e in recorder.events) / 1000.0:.3f}",
        )

        for e in recorder.events:
            tc = ET.SubElement(
                testsuite,
                "testcase",
                classname=f"Tools.{e.tool_name}",
                name=f"call_{e.global_index}_{e.tool_name}",
                time=f"{e.duration_ms / 1000.0:.3f}",
            )
            if e.fault_injected is not None:
                fail = ET.SubElement(
                    tc,
                    "failure",
                    message=f"Injected Fault: {e.fault_injected.value}",
                    type="InjectedFault",
                )
                fail.text = f"Tool '{e.tool_name}' faulted: {e.error or 'Injected fault'}"

    tree = ET.ElementTree(testsuites)
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True)
    return str(out_path.resolve())
