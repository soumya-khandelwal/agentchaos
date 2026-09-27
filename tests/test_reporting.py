"""Tests for HTML report generator and JUnit XML exporter."""

import xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from agent_chaos.core.faults import Fault
from agent_chaos.core.interceptor import ChaosHarness
from agent_chaos.reporting.html_report import generate_html_report
from agent_chaos.reporting.junit_export import export_junit_xml
from agent_chaos.security.redteam import RedTeamSuite


def test_html_report_generation(tmp_path: Path):
    harness = ChaosHarness()
    harness.set_fault("payment_api", Fault.http_error(504))

    @harness.intercept(tool_name="payment_api")
    def payment_api(amount: float):
        return "success"

    try:
        payment_api(amount=100.0)
    except Exception:
        pass

    out_file = tmp_path / "test-report.html"
    path = generate_html_report(harness, output_file=str(out_file))

    assert Path(path).exists()
    content = Path(path).read_text(encoding="utf-8")
    assert "<title>AgentChaos Reliability & Blast-Radius Report</title>" in content
    assert "payment_api" in content
    assert "504" in content or "HTTP_ERROR" in content


def test_junit_xml_export(tmp_path: Path):
    harness = ChaosHarness()
    harness.set_fault("auth_service", Fault.timeout(1.0))

    @harness.intercept(tool_name="auth_service")
    def auth_service(token: str):
        return True

    try:
        auth_service(token="abc")
    except Exception:
        pass

    out_file = tmp_path / "test-junit.xml"
    path = export_junit_xml(harness, output_file=str(out_file))

    assert Path(path).exists()
    tree = ET.parse(path)
    root = tree.getroot()
    assert root.tag == "testsuites"
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.get("name") == "AgentChaos.ReliabilitySuite"
    assert int(suite.get("tests", 0)) >= 1


def test_redteam_html_and_junit_export(tmp_path: Path):
    suite = RedTeamSuite(target_tool="lookup", forbidden_tools=["delete_account"])

    def agent(harness: ChaosHarness):
        @harness.intercept(tool_name="lookup")
        def lookup(key: str):
            return "data"

        lookup("query")

    report = suite.run(agent)

    # Export HTML
    html_path = generate_html_report(report, output_file=str(tmp_path / "redteam.html"))
    assert Path(html_path).exists()
    html_content = Path(html_path).read_text(encoding="utf-8")
    assert "Automated Indirect Prompt Injection & Tool Vulnerability Matrix" in html_content
    assert "Resilience Score" in html_content

    # Export JUnit
    xml_path = export_junit_xml(report, output_file=str(tmp_path / "redteam.xml"))
    assert Path(xml_path).exists()
    tree = ET.parse(xml_path)
    root = tree.getroot()
    suite_node = root.find("testsuite")
    assert suite_node is not None
    assert suite_node.get("name") == "AgentChaos.SecurityRedTeam"
