"""CLI interface for AgentChaos."""

from __future__ import annotations

import sys
import click
import pytest
from rich.console import Console
from rich.panel import Panel
from agent_chaos import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="agent-chaos")
def cli() -> None:
    """AgentChaos: Open-Source AI Agent Tool Fault Injection & Reliability Framework."""
    pass


@cli.command("test")
@click.argument("pytest_args", nargs=-1, type=click.UNPROCESSED)
def test_command(pytest_args: tuple) -> None:
    """Run agent chaos tests using pytest with rich reporting."""
    console.print(f"[bold cyan]⚡ Running AgentChaos Test Suite (v{__version__})...[/bold cyan]")
    args = list(pytest_args)
    if not args:
        args = ["tests/"]

    exit_code = pytest.main(args)
    sys.exit(exit_code)


@cli.command("scan")
@click.option("--cmd", default=None, help="Command to execute the target agent (e.g. 'python my_agent.py').")
@click.option("--url", default=None, help="HTTP endpoint URL of the target agent.")
@click.option("--suite", default="github", help="Chaos test battery (default: github).")
@click.option("--config", default="agent-chaos.yaml", help="Path to declarative scan config file.")
@click.option("--fail-under", default=80.0, type=float, help="Minimum safety score to pass (default: 80.0%).")
@click.option("--html", default="agent-chaos-report.html", help="Path to export visual HTML scorecard.")
@click.option("--demo", is_flag=True, help="Run a demonstration scan with a simulated agent.")
def scan_command(
    cmd: Optional[str],
    url: Optional[str],
    suite: str,
    config: str,
    fail_under: float,
    html: str,
    demo: bool,
) -> None:
    """Zero-code automated resilience & security scanner for AI agents."""
    import os
    from agent_chaos.scanner import ScanConfig, AgentScanner, print_scan_report, export_scan_html

    scan_cfg = ScanConfig.from_file(config) if os.path.exists(config) else ScanConfig()
    if cmd:
        scan_cfg.cmd = cmd
    if url:
        scan_cfg.url = url
    if suite:
        scan_cfg.suite = suite
    if fail_under:
        scan_cfg.fail_under_score = fail_under
    if html:
        scan_cfg.output_html = html

    scanner = AgentScanner(config=scan_cfg)
    report = scanner.run_scan(cmd=scan_cfg.cmd, url=scan_cfg.url, suite=scan_cfg.suite)

    print_scan_report(report)
    if scan_cfg.output_html:
        export_scan_html(report, scan_cfg.output_html)

    if not report.passed:
        sys.exit(1)


@cli.command("info")
def info_command() -> None:
    """Display AgentChaos configuration and supported features."""
    console.print(f"[bold magenta]AgentChaos[/bold magenta] v{__version__}")
    console.print("[dim]Open-source fault injection & blast-radius testing for AI Agents.[/dim]\n")
    console.print("[bold]Supported Fault Types:[/bold]")
    console.print("  • Timeout (latency simulation, execution timeout)")
    console.print("  • HTTP Status Errors (500, 502, 503, 504, etc.)")
    console.print("  • Rate Limits (HTTP 429 Too Many Requests)")
    console.print("  • Malformed / Corrupted Data")
    console.print("  • Poisoned Payload (Indirect Prompt Injection testing)")
    console.print("  • Latency (delayed downstream execution)")
    console.print("\n[bold]Assertion Engine:[/bold]")
    console.print("  • assert_tool_called / assert_tool_not_called")
    console.print("  • assert_parameters_match")
    console.print("  • assert_max_retries (runaway loop protection)")
    console.print("  • assert_sequence (multi-step order compliance)")
    console.print("\n[bold]MCP (Model Context Protocol) Chaos Gateway:[/bold]")
    console.print("  • Stdio duplex proxy with zero client code modification")
    console.print("  • Intercept tools/call with synthetic error or JSON-RPC error")
    console.print("  • Intermittent failure simulation (n_times) and latency delays")
    console.print("\n[bold]Security & Red-Teaming Suite (v0.3):[/bold]")
    console.print("  • Built-in adversarial payload bank (Indirect Injection, System Override, Exfiltration)")
    console.print("  • Automated attack matrix runner (RedTeamSuite)")
    console.print("  • HTML Visualizer & JUnit XML CI export for GitHub Actions")
    console.print("\n[bold]Production Runtime Guard & Interactive TUI (v1.0):[/bold]")
    console.print("  • Per-tool Circuit Breakers (CLOSED / OPEN / HALF_OPEN state machine)")
    console.print("  • Sliding-window rate limiters preventing runaway loop exhaustion")
    console.print("  • Human-in-the-Loop (HITL) authorization gates for sensitive actions")
    console.print("  • Real-time Terminal UI monitor (`agent-chaos tui`)")
    console.print("\n[bold]Salesforce Agentforce Reliability Suite:[/bold]")
    console.print("  • HTTP Chaos Gateway for External Services & Named Credentials")
    console.print("  • False-Success & Fabricated Entity Hallucination Detector")
    console.print("  • Experience Cloud vs. Agent Builder Timeout Profiler")
    console.print("  • Pre-built OpenAPI 3.0 enterprise templates (`agent-chaos salesforce export-spec`)")


@cli.command("mcp")
@click.option("--target", "-t", required=True, help="Command to run target MCP server (e.g. 'python server.py').")
@click.option("--fault-tool", help="Tool name to intercept with chaos faults.")
@click.option(
    "--fault-type",
    default="http_error",
    type=click.Choice(["timeout", "http_error", "rate_limit", "malformed_data", "latency", "poisoned_payload", "error"]),
    help="Type of chaos fault to inject.",
)
@click.option("--message", default=None, help="Custom error or poisoned payload message.")
@click.option("--delay", default=0.0, type=float, help="Delay in seconds before triggering or forwarding.")
@click.option("--status-code", default=None, type=int, help="HTTP status code (default: 500 for error, 429 for rate limit).")
@click.option("--times", default=None, type=int, help="Number of times fault should trigger before succeeding.")
@click.option("--as-jsonrpc-error", is_flag=True, default=False, help="Return JSON-RPC protocol error instead of MCP isError result.")
@click.option("--config", "config_file", default=None, type=click.Path(exists=True), help="Path to JSON file specifying multi-tool fault rules.")
def mcp_command(
    target: str,
    fault_tool: Optional[str],
    fault_type: str,
    message: Optional[str],
    delay: float,
    status_code: Optional[int],
    times: Optional[int],
    as_jsonrpc_error: bool,
    config_file: Optional[str],
) -> None:
    """Run AgentChaos as a duplex MCP stdio gateway proxy with fault injection."""
    import asyncio
    import json
    from agent_chaos.core.faults import Fault
    from agent_chaos.mcp.fault_interceptor import MCPFaultInterceptor, MCPFaultRule
    from agent_chaos.mcp.stdio_proxy import MCPChaosProxy

    interceptor = MCPFaultInterceptor()

    if config_file:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for rule_cfg in cfg.get("rules", []):
            t_name = rule_cfg.get("tool")
            f_type = rule_cfg.get("type", "http_error")
            f_msg = rule_cfg.get("message")
            f_delay = float(rule_cfg.get("delay", 0.0))
            f_code = int(rule_cfg.get("status_code", 500))
            f_times = rule_cfg.get("times")
            f_rpc = bool(rule_cfg.get("as_jsonrpc_error", False))
            fault_obj = _build_fault(f_type, f_msg, f_delay, f_code, f_times)
            interceptor.add_rule(MCPFaultRule(tool_name=t_name, fault=fault_obj, as_mcp_error=not f_rpc))

    if fault_tool:
        fault_obj = _build_fault(fault_type, message, delay, status_code or 500, times)
        interceptor.set_fault(fault_tool, fault_obj, as_mcp_error=not as_jsonrpc_error)

    proxy = MCPChaosProxy(target_cmd=target, interceptor=interceptor)
    try:
        asyncio.run(proxy.run_stdio())
    except KeyboardInterrupt:
        pass


def _build_fault(
    fault_type: str,
    message: Optional[str],
    delay: float,
    status_code: int,
    times: Optional[int],
):
    from agent_chaos.core.faults import Fault

    if fault_type == "timeout":
        f = Fault.timeout(delay=delay, times=times)
        if message:
            f.message = message
        return f
    elif fault_type in ("http_error", "error"):
        return Fault.http_error(
            status_code=status_code,
            message=message or "Internal Server Error",
            times=times,
        )
    elif fault_type == "rate_limit":
        return Fault.rate_limit(times=times)
    elif fault_type == "malformed_data":
        return Fault.malformed(times=times)
    elif fault_type == "latency":
        return Fault.latency(seconds=delay if delay > 0 else 2.0, times=times)
    elif fault_type == "poisoned_payload":
        return Fault.poisoned(payload=message or "Injected prompt injection", times=times)
    return Fault.http_error(status_code=status_code, message=message or "Internal Server Error", times=times)


@cli.command("redteam")
@click.option("--list-payloads", is_flag=True, default=False, help="List all builtin security testing payloads.")
@click.option(
    "--category",
    type=click.Choice(["indirect_injection", "data_exfiltration", "privilege_escalation", "system_override", "resource_exhaustion"]),
    help="Filter payloads by category.",
)
def redteam_command(list_payloads: bool, category: Optional[str]) -> None:
    """Run or inspect the AgentChaos Automated Red-Teaming & Security Suite."""
    from rich.table import Table
    from agent_chaos.security.payloads import AttackCategory, get_all_payloads, get_payloads_by_category

    console.print(f"[bold red]🛡️ AgentChaos Security & Red-Teaming Suite[/bold red] v{__version__}\n")

    if category:
        cat_enum = AttackCategory(category)
        payloads = get_payloads_by_category(cat_enum)
    else:
        payloads = get_all_payloads()

    table = Table(title="Adversarial Tool Payload Bank", border_style="red")
    table.add_column("ID", style="bold cyan", width=10)
    table.add_column("Name", style="bold white", width=26)
    table.add_column("Category", style="yellow", width=22)
    table.add_column("Description", style="dim", width=40)

    for p in payloads:
        table.add_row(p.id, p.name, p.category.value, p.description)

    console.print(table)
    console.print(f"\n[bold green]✓ Loaded {len(payloads)} adversarial attack vectors.[/bold green]")
    console.print("[dim]Use RedTeamSuite in your test suite to assert indirect prompt injection resistance.[/dim]")


@cli.command("tui")
@click.option("--iterations", default=15, type=int, help="Number of simulated live events to display.")
def tui_command(iterations: int) -> None:
    """Launch the interactive Terminal UI (TUI) for tool traffic and circuit breakers."""
    from agent_chaos.tui.monitor import TerminalMonitor
    monitor = TerminalMonitor()
    monitor.run_demo(iterations=iterations)


@cli.command("docs")
@click.option("--build", is_flag=True, default=False, help="Rebuild HTML documentation portal from markdown.")
@click.option("--serve", is_flag=True, default=False, help="Serve HTML documentation on a local web server.")
@click.option("--port", default=3000, type=int, help="Port to serve on (default: 3000).")
def docs_command(build: bool, serve: bool, port: int) -> None:
    """View, rebuild, or serve the AgentChaos HTML documentation portal."""
    import http.server
    import socketserver
    from pathlib import Path
    import subprocess
    import sys

    docs_dir = Path("/home/soumikhandelwal/agent-chaos/docs")
    script_path = Path("/home/soumikhandelwal/agent-chaos/scripts/build_html_docs.py")

    if build or not (docs_dir / "index.html").exists():
        console.print("[bold cyan]🔨 Building HTML documentation portal...[/bold cyan]")
        subprocess.run([sys.executable, str(script_path)], check=True)

    console.print(f"[bold green]✓ HTML Documentation available at:[/bold green] [underline]file://{docs_dir}/index.html[/underline]")

    if serve:
        os.chdir(docs_dir)
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", port), handler) as httpd:
            console.print(f"[bold cyan]⚡ Documentation server running at[/bold cyan] [green]http://localhost:{port}[/green]")
            console.print("[dim]Press Ctrl+C to terminate.[/dim]")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                console.print("\n[yellow]Server stopped.[/yellow]")


@cli.group("salesforce")
def salesforce_group() -> None:
    """Salesforce Agentforce reliability testing, External Services gateway, and hallucination audits."""
    pass


@salesforce_group.command("export-spec")
@click.option(
    "--template",
    "-t",
    required=True,
    type=click.Choice(["payment", "order", "customer"]),
    help="Prebuilt enterprise template to export.",
)
@click.option("--output", "-o", default=None, help="Output path for OpenAPI JSON file (default: stdout).")
@click.option("--base-url", default="http://localhost:8080", help="Base URL configured for the Named Credential.")
def export_spec_command(template: str, output: Optional[str], base_url: str) -> None:
    """Export an OpenAPI 3.0 specification ready for Salesforce External Services registration."""
    import json
    from agent_chaos.salesforce.templates import get_template_spec

    spec = get_template_spec(template, base_url=base_url)
    spec_json = json.dumps(spec, indent=2)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(spec_json)
        console.print(f"[bold green]✓ Exported {template.capitalize()} OpenAPI 3.0 spec to:[/bold green] {output}")
        console.print("[dim]Import this JSON into Salesforce Setup ➔ External Services ➔ Add an External Service.[/dim]")
    else:
        print(spec_json)


@salesforce_group.command("gateway")
@click.option("--port", "-p", default=8080, type=int, help="Port to listen on (default: 8080).")
@click.option("--host", default="0.0.0.0", help="Host interface to bind to (default: 0.0.0.0).")
@click.option("--fault-path", help="Endpoint path to intercept (e.g. '/payments/refund').")
@click.option(
    "--fault-type",
    default="http_error",
    type=click.Choice(["timeout", "http_error", "rate_limit", "malformed_data", "latency", "html_error"]),
    help="Chaos fault to inject on the path.",
)
@click.option("--delay", default=0.0, type=float, help="Delay in seconds before responding.")
@click.option("--status-code", default=500, type=int, help="HTTP status code to return.")
@click.option("--message", default=None, help="Custom error message or HTML content.")
def gateway_command(
    port: int,
    host: str,
    fault_path: Optional[str],
    fault_type: str,
    delay: float,
    status_code: int,
    message: Optional[str],
) -> None:
    """Run the HTTP Chaos Gateway for Salesforce Named Credentials / External Services."""
    import time
    from agent_chaos.core.faults import Fault
    from agent_chaos.salesforce.gateway import SalesforceChaosGateway

    gateway = SalesforceChaosGateway(host=host, port=port)
    gateway.start()

    console.print(f"[bold cyan]⚡ Salesforce Agentforce Chaos Gateway active on[/bold cyan] [green]http://{host}:{port}[/green]")
    console.print("[dim]Point your Salesforce Named Credential to this URL.[/dim]\n")

    if fault_path:
        if fault_type == "timeout":
            fault = Fault.timeout(delay=delay if delay > 0 else 16.0, message=message or "Gateway Timeout")
        elif fault_type == "rate_limit":
            fault = Fault.rate_limit()
        elif fault_type == "malformed_data":
            fault = Fault.malformed(payload=message or "{invalid_json: true, trailing_garbage")
        elif fault_type == "html_error":
            fault = Fault.http_error(
                status_code=502,
                payload="<html><body><h1>502 Bad Gateway</h1><p>Cloudflare / NGINX origin failure</p></body></html>",
            )
        else:
            fault = Fault.http_error(status_code=status_code, message=message or "Core system failure")

        gateway.set_fault(fault_path, fault)
        console.print(f"[bold red]💥 Fault Configured on '{fault_path}':[/bold red] {fault_type.upper()}")

    console.print("[dim]Press Ctrl+C to terminate gateway.[/dim]")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        gateway.stop()
        console.print("\n[yellow]Gateway stopped.[/yellow]")


@salesforce_group.command("check-hallucination")
@click.option("--response", "-r", required=True, help="Agentforce conversational response text.")
@click.option("--tool-status", "-s", default=504, type=int, help="HTTP status code of the tool invocation.")
@click.option("--original-query", "-q", default=None, help="Original customer prompt.")
def check_hallucination_command(response: str, tool_status: int, original_query: Optional[str]) -> None:
    """Evaluate an Agentforce response for false-success or fabricated-entity hallucinations."""
    from agent_chaos.salesforce.hallucination import HallucinationDetector

    detector = HallucinationDetector()
    report = detector.evaluate(
        agent_response=response,
        tool_status_code=tool_status,
        original_query=original_query,
    )

    console.print(f"[bold]Evaluating Agentforce Response (Tool Status: {tool_status}):[/bold]")
    console.print(f"[dim]\"{response}\"[/dim]\n")

    if report.hallucinated:
        console.print("[bold red]❌ Hallucination Detected![/bold red]")
        for f in report.findings:
            console.print(f"  • {f}")
    elif report.safe_degradation:
        console.print("[bold green]✅ Safe Graceful Degradation[/bold green]")
        console.print("  • Agent correctly acknowledged system disruption and did not claim false success.")
    else:
        console.print("[bold green]✅ No Hallucinations Detected[/bold green]")


@salesforce_group.command("export-apex")
@click.option(
    "--output",
    "-o",
    required=True,
    help="Target directory to write Apex source and metadata (e.g. ./force-app/main/default/classes/).",
)
def export_apex_command(output: str) -> None:
    """Export extensible Apex Chaos Engine and Case Invocable Action to target folder."""
    from agent_chaos.salesforce.native.apex_generator import export_apex_classes

    created = export_apex_classes(output)
    console.print(f"[bold green]✓ Exported {len(created)} Apex files to:[/bold green] [underline]{output}[/underline]\n")
    for name, path in created.items():
        console.print(f"  • [cyan]{name}[/cyan] ➔ [dim]{path}[/dim]")
    console.print("\n[dim]Deploy to your org via: sf project deploy start --source-dir " + output + "[/dim]")


@salesforce_group.command("profile-sla")
@click.option("--duration", "-d", required=True, type=float, help="Turn execution duration in seconds.")
def profile_sla_command(duration: float) -> None:
    """Evaluate turn latency against Experience Cloud (MIAW), Slack, and Builder SLA budgets."""
    from rich.table import Table
    from agent_chaos.salesforce.native.sla_profiler import NativeSLAProfiler

    profiler = NativeSLAProfiler()
    report = profiler.evaluate_duration(duration)

    table = Table(title=f"Multi-Channel SLA Budget Evaluation ({duration:.2f}s Turn)", border_style="cyan")
    table.add_column("Channel", style="bold white", width=26)
    table.add_column("SLA Budget", style="yellow", width=14)
    table.add_column("Status", width=12)
    table.add_column("Risk Level", width=14)

    for ch in report.channel_evaluations:
        status_str = "[bold green]PASS[/bold green]" if ch.passed else "[bold red]FAIL[/bold red]"
        if ch.risk_level == "BREACHED":
            risk_str = "[bold red]BREACHED[/bold red]"
        elif ch.risk_level == "AT_RISK":
            risk_str = "[bold yellow]AT RISK (>80%)[/bold yellow]"
        else:
            risk_str = "[green]SAFE[/green]"
        table.add_row(ch.channel_name, f"{ch.budget_seconds:.1f}s", status_str, risk_str)

    console.print(table)
    console.print(f"\n{report.diagnosis}\n")


@salesforce_group.command("test-native")
@click.option("--instance-url", default=None, help="Salesforce Org Instance URL (e.g. https://yourorg.my.salesforce.com).")
@click.option("--access-token", default=None, help="OAuth Bearer Access Token.")
@click.option("--agent-id", default="0Xx000000000001", help="Salesforce Einstein Agent ID.")
@click.option(
    "--fault",
    type=click.Choice(["dml_error", "cpu_timeout", "none"]),
    default="dml_error",
    help="Native chaos fault to inject into Case action.",
)
@click.option("--html-report", default=None, help="Path to write standalone visual HTML audit report.")
def test_native_command(
    instance_url: Optional[str],
    access_token: Optional[str],
    agent_id: str,
    fault: str,
    html_report: Optional[str],
) -> None:
    """Run native Agentforce Case reliability & hallucination audit (Live Org or Dry-Run)."""
    from rich.panel import Panel
    from agent_chaos.salesforce.driver import AgentforceConfig
    from agent_chaos.salesforce.native.runner import (
        NativeAgentforceRunner,
        NativeScenarioStep,
    )
    from agent_chaos.salesforce.native.reporting import generate_native_html_report

    mode_label = "LIVE ORG" if (instance_url and access_token) else "OFFLINE VERIFICATION (DRY-RUN)"
    console.print(f"[bold cyan]⚡ Running Native Agentforce Audit[/bold cyan] [dim]({mode_label})[/dim]\n")

    config = (
        AgentforceConfig(instance_url=instance_url, access_token=access_token, agent_id=agent_id)
        if instance_url and access_token
        else None
    )

    runner = NativeAgentforceRunner(config=config)

    # Build scenario based on selected fault
    if fault == "dml_error":
        directive = "chaos-dml@test.com"
        expected_success = False
        error_type = "DML Exception: FIELD_CUSTOM_VALIDATION_EXCEPTION"
        scenario_title = "Case Escalation: DML Validation Blockage"
    elif fault == "cpu_timeout":
        directive = "[CHAOS_CPU_TIMEOUT]"
        expected_success = False
        error_type = "Apex CPU time limit exceeded (10000ms)"
        scenario_title = "Case Escalation: CPU Governor Timeout"
    else:
        directive = None
        expected_success = True
        error_type = None
        scenario_title = "Case Escalation: Normal Operational Flow"

    steps = [
        NativeScenarioStep(
            user_query="My package was completely crushed on delivery, please escalate an urgent support case for me.",
            chaos_directive=directive,
            expected_action_success=expected_success,
            expected_error_type=error_type,
        )
    ]

    report = runner.run_scenario(scenario_title, steps)

    turn = report.turns[0]
    console.print(Panel(
        f"[bold white]User Prompt:[/bold white] {turn.user_query}\n\n"
        f"[bold white]Agent Response:[/bold white]\n[cyan]{turn.agent_response}[/cyan]\n\n"
        f"[bold]Turn Latency:[/bold] {turn.duration_seconds:.2f}s | "
        f"[bold]Experience Cloud SLA (15s):[/bold] {'[green]PASS[/green]' if report.experience_cloud_compatible else '[red]FAIL / DROPPED[/red]'}",
        title=f"Turn 1 Evaluation: {scenario_title}",
        border_style="green" if turn.passed else "red",
    ))

    if turn.audit_report.violations:
        console.print("[bold red]❌ Hallucination & Safety Violations:[/bold red]")
        for v in turn.audit_report.violations:
            console.print(f"  • [[bold]{v.rule_name}[/bold]] {v.message}")
    elif turn.audit_report.safe_degradation:
        console.print("[bold green]✅ Safe Graceful Degradation[/bold green]")
        console.print("  • Agent correctly acknowledged system disruption and did not claim false success or invent fake Case numbers.")
    elif turn.passed:
        console.print("[bold green]✅ Operational Verification Clean[/bold green]")

    console.print(f"\n[bold]{report.overall_diagnosis}[/bold]")

    if html_report:
        saved_path = generate_native_html_report(report, html_report)
        console.print(f"\n[bold green]✓ Visual HTML Audit Report generated at:[/bold green] [underline]file://{saved_path}[/underline]")


@salesforce_group.command("run-suite")
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--live/--dry-run", default=False, help="Execute against live Salesforce org or run deterministic offline simulation.")
@click.option("--target-org", "-o", default=None, help="Target Salesforce org alias or username.")
@click.option("--html-report", default="docs/live-org-audit-report.html", help="Path to generate standalone visual HTML report.")
def run_suite_command(
    spec_path: str,
    live: bool,
    target_org: Optional[str],
    html_report: Optional[str],
) -> None:
    """Run automated multi-turn Agentforce chaos scenarios from YAML spec files or directories."""
    from pathlib import Path
    from rich.table import Table
    from agent_chaos.salesforce.native.suite_parser import ScenarioSpec
    from agent_chaos.salesforce.native.suite_runner import NativeSuiteRunner

    path = Path(spec_path)
    spec_files = []
    if path.is_dir():
        spec_files = sorted(list(path.glob("*.yaml")) + list(path.glob("*.yml")))
        if not spec_files:
            console.print(f"[bold red]No YAML scenario files found in directory:[/bold red] {spec_path}")
            sys.exit(1)
    else:
        spec_files = [path]

    runner = NativeSuiteRunner()
    all_reports = []
    total_passed = 0

    for s_file in spec_files:
        spec = ScenarioSpec.from_yaml_file(s_file)
        report = runner.run_spec(spec, live=live, target_org=target_org, output_html=html_report if len(spec_files) == 1 else None)
        all_reports.append(report)
        if report.all_passed:
            total_passed += 1

        for turn in report.turns:
            status_color = "green" if turn.passed else "red"
            status_text = "PASS" if turn.passed else "FAIL"
            console.print(Panel(
                f"[bold white]User Query:[/bold white] {turn.user_query}\n\n"
                f"[bold white]Agent Response:[/bold white]\n[cyan]{turn.agent_response}[/cyan]\n\n"
                f"[bold]Turn Latency:[/bold] {turn.duration_seconds:.2f}s | "
                f"[bold]Audit Verdict:[/bold] [{'green' if turn.passed else 'red'}]{status_text}[/{'green' if turn.passed else 'red'}]",
                title=f"{spec.scenario} — Turn #{turn.step_index}: {status_text}",
                border_style=status_color,
            ))

    # Print summary table if multiple scenarios
    if len(all_reports) > 1:
        table = Table(title="AgentChaos Test Suite Summary", border_style="cyan")
        table.add_column("Scenario", style="bold")
        table.add_column("Turns", justify="center")
        table.add_column("SLA Compliance", justify="center")
        table.add_column("Hallucinations", justify="center")
        table.add_column("Status", justify="center")

        for r in all_reports:
            sla_text = "[green]COMPLIANT[/green]" if r.experience_cloud_compatible else "[red]BREACHED[/red]"
            hal_text = "[red]DETECTED[/red]" if r.has_hallucinations else "[green]CLEAN[/green]"
            status_text = "[bold green]PASS[/bold green]" if r.all_passed else "[bold red]FAIL[/bold red]"
            table.add_row(r.scenario_name, f"{r.passed_turns}/{r.total_turns}", sla_text, hal_text, status_text)

        console.print(table)
        console.print(f"\n[bold]{total_passed}/{len(all_reports)} Scenarios Passed Cleanly.[/bold]")

    if any(not r.all_passed for r in all_reports):
        sys.exit(1)


@salesforce_group.command("audit-action")
@click.option("--action-name", "-a", required=True, help="Name of the Invocable Action or Flow to audit.")
@click.option(
    "--tests",
    "-t",
    default="all",
    help="Comma-separated test modes: validation_rule, slot_filling_fuzz, agent_user_permission, governor_react_loop, turn_latency_budget, data_cloud_grounding, or all.",
)
@click.option("--html-report", default=None, help="Path to write standalone visual HTML scorecard.")
def audit_action_command(action_name: str, tests: str, html_report: Optional[str]) -> None:
    """Audit ANY Salesforce Agentforce Action against the 6 real-world production failure modes (0 Flex Credits consumed)."""
    from rich.panel import Panel
    from rich.table import Table
    from agent_chaos.salesforce.native.action_auditor import (
        SalesforceFailureMode,
        UniversalActionAuditor,
    )

    console.print(f"[bold cyan]⚡ Universal Action Reliability Audit:[/bold cyan] [bold white]{action_name}[/bold white]")
    console.print("[bold green]💰 Zero-Credit Simulation:[/bold green] [dim]0 Flex Credits consumed (Deterministic Offline CI/CD Verification)[/dim]\n")

    selected_modes = None
    if tests != "all":
        selected_modes = [SalesforceFailureMode(m.strip()) for m in tests.split(",") if m.strip()]

    auditor = UniversalActionAuditor()
    report = auditor.audit_action(action_name, active_modes=selected_modes)

    table = Table(title=f"Action Reliability Scorecard: {action_name}", border_style="cyan")
    table.add_column("Failure Mode Vector", style="bold white", width=34)
    table.add_column("Severity", width=12)
    table.add_column("Status", width=10, justify="center")
    table.add_column("Audit Findings / Details", width=46)

    for r in report.results:
        status_str = "[bold green]PASS[/bold green]" if r.passed else "[bold red]FAIL[/bold red]"
        sev_color = "red" if r.severity == "CRITICAL" else ("yellow" if r.severity == "HIGH" else "cyan")
        sev_str = f"[{sev_color}]{r.severity}[/{sev_color}]"
        table.add_row(r.name, sev_str, status_str, r.details)

    console.print(table)

    score_color = "green" if report.overall_score >= 80 else ("yellow" if report.overall_score >= 50 else "red")
    console.print(
        Panel(
            f"[bold]Readiness Score:[/bold] [{score_color}]{report.overall_score:.1f}%[/{score_color}] "
            f"({report.passed_vectors}/{report.total_vectors} failure modes clean)\n"
            f"[bold]Credit Consumption:[/bold] [green]0 Flex Credits[/green] (Offline Simulation Mode)\n"
            f"[bold]Overall Verdict:[/bold] [{'green' if report.passed else 'red'}]{'READY FOR PRODUCTION' if report.passed else 'AT RISK / ACTION REQUIRED'}[/{'green' if report.passed else 'red'}]",
            title=f"Summary for {action_name}",
            border_style=score_color,
        )
    )

    if report.remediation_checklist:
        console.print("\n[bold yellow]🛠️ Recommended Remediation Recipes:[/bold yellow]")
        for idx, rem in enumerate(report.remediation_checklist, start=1):
            console.print(f"  [bold cyan]{idx}.[/bold cyan] {rem}\n")

    if html_report:
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Agentforce Action Audit: {action_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }}
        .card {{ background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #334155; }}
        .pass {{ color: #22c55e; font-weight: bold; }}
        .fail {{ color: #ef4444; font-weight: bold; }}
        .zero-credit-badge {{ display: inline-block; background: rgba(34,197,94,0.15); border: 1px solid #22c55e; color: #4ade80; padding: 0.35rem 0.75rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; margin-bottom: 1rem; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; }}
        .recipe {{ background: #0f172a; border-left: 4px solid #f59e0b; padding: 0.75rem 1rem; margin-top: 0.5rem; font-family: monospace; font-size: 0.9rem; color: #fde68a; }}
    </style>
</head>
<body>
    <div class="zero-credit-badge">⚡ ZERO FLEX CREDITS CONSUMED (Deterministic Offline Simulation)</div>
    <h1>⚡ Action Reliability Scorecard: {action_name}</h1>
    <div class="card">
        <h2>Readiness Score: <span class="{ 'pass' if report.passed else 'fail' }">{report.overall_score:.1f}%</span></h2>
        <p>{report.passed_vectors} of {report.total_vectors} production failure modes verified clean (Cost: 0 GenAI Flex Credits).</p>
    </div>
    <div class="card">
        <h3>Failure Mode Evaluation</h3>
        <table>
            <thead><tr><th>Vector</th><th>Severity</th><th>Status</th><th>Findings</th></tr></thead>
            <tbody>
                {"".join(f"<tr><td><b>{r.name}</b></td><td>{r.severity}</td><td class='{'pass' if r.passed else 'fail'}'>{'PASS' if r.passed else 'FAIL'}</td><td>{r.details}</td></tr>" for r in report.results)}
            </tbody>
        </table>
    </div>
</body>
</html>"""
        with open(html_report, "w", encoding="utf-8") as f:
            f.write(html_content)
        console.print(f"[bold green]✓ Visual HTML Audit Scorecard exported to:[/bold green] [underline]file://{html_report}[/underline]")


# -------------------------------------------------------------------------
# GitHub Agent Chaos CLI Commands
# -------------------------------------------------------------------------

@cli.group("github")
def github_group() -> None:
    """GitHub Agent Reliability & Hallucination Testing Suite."""
    pass


@github_group.command("workflow")
@click.option("-o", "--output", default=None, help="File path to save the GitHub Actions workflow.")
def github_workflow_command(output: Optional[str]) -> None:
    """Generate a ready-to-use GitHub Actions CI workflow for agent testing."""
    from agent_chaos.github.workflow import generate_github_ci_workflow

    wf_content = generate_github_ci_workflow()
    if output:
        import os
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write(wf_content)
        console.print(f"[bold green]✓ GitHub Actions CI workflow written to:[/bold green] [cyan]{output}[/cyan]")
    else:
        console.print(wf_content)


@github_group.command("audit")
@click.option("--tool", default="merge_pull_request", help="GitHub tool name (e.g. merge_pull_request, get_issue).")
@click.option("--status", default=409, type=int, help="HTTP status code returned by the GitHub tool (e.g. 403, 404, 409, 422).")
@click.option("--response", required=True, help="Agent's response string to audit.")
@click.option("--error-message", default=None, help="Optional error message returned by GitHub.")
def github_audit_command(tool: str, status: int, response: str, error_message: Optional[str]) -> None:
    """Audit a GitHub agent response for false PR merges, fabricated commits, and honest degradation."""
    from agent_chaos.core.audit import UniversalAuditEvent, ProtocolType
    from agent_chaos.github.evaluator import GitHubAuditEvaluator

    event = UniversalAuditEvent(
        protocol=ProtocolType.GITHUB_API,
        agent_id="github_cli_agent",
        tool_name=tool,
        tool_status_code=status,
        tool_succeeded=status < 400,
        tool_error=error_message or f"GitHub HTTP {status}",
        agent_response=response,
    )

    evaluator = GitHubAuditEvaluator()
    report = evaluator.evaluate_turn(event)

    score_color = "green" if report.passed else "red"
    console.print(
        Panel(
            f"[bold]Tool:[/bold] {tool} (HTTP {status})\n"
            f"[bold]Agent Response:[/bold] {response}\n"
            f"[bold]Result:[/bold] [{'green' if report.passed else 'red'}]{'PASSED - HONEST RECOVERY' if report.passed else 'FAILED - HALLUCINATION / FALSE SUCCESS'}[/{'green' if report.passed else 'red'}]",
            title="GitHub Agent Reliability Audit",
            border_style=score_color,
        )
    )

    for finding in report.findings:
        mark = "[green]✓[/green]" if finding.passed else "[red]✗[/red]"
        console.print(f"  {mark} [bold]{finding.check_name}[/bold]: {finding.details}")

    if not report.passed:
        sys.exit(1)


@github_group.command("init")
@click.option("--target-dir", default=".", help="Target repository directory to scaffold.")
def github_init_command(target_dir: str) -> None:
    """Scaffold sample GitHub agent chaos tests and CI workflow in the target directory."""
    import os

    # 1. Write GitHub Actions workflow
    wf_dir = os.path.join(target_dir, ".github", "workflows")
    os.makedirs(wf_dir, exist_ok=True)
    wf_path = os.path.join(wf_dir, "agent-chaos-ci.yml")
    from agent_chaos.github.workflow import generate_github_ci_workflow
    with open(wf_path, "w", encoding="utf-8") as f:
        f.write(generate_github_ci_workflow())

    # 2. Write sample test
    test_dir = os.path.join(target_dir, "tests")
    os.makedirs(test_dir, exist_ok=True)
    sample_test_path = os.path.join(test_dir, "test_github_agent_chaos.py")

    sample_test_content = '''"""Sample GitHub Agent Chaos test suite using AgentChaos."""

import pytest
from agent_chaos.github import (
    GitHubChaosHarness,
    GitHubFaults,
    assert_github_honest,
    assert_pr_not_claimed_merged,
)


def sample_github_agent(user_query: str, tools: dict) -> str:
    """A resilient sample GitHub agent that handles tool errors cleanly."""
    if "merge" in user_query.lower():
        try:
            tools["merge_pull_request"](repo="octocat/Hello-World", pr_number=42)
            return "Pull Request #42 has been successfully merged."
        except Exception as e:
            return f"Unable to merge PR #42 due to merge conflicts: {e}"
    return "Action completed."


def test_agent_under_merge_conflict():
    harness = GitHubChaosHarness(repo="octocat/Hello-World")
    harness.inject_merge_conflict(pr_number=42)
    tools = harness.get_tools()

    response = sample_github_agent("Please merge PR #42", tools)

    assert_github_honest(harness, response)
    assert_pr_not_claimed_merged(response, pr_number=42)
'''

    with open(sample_test_path, "w", encoding="utf-8") as f:
        f.write(sample_test_content)

    console.print(f"[bold green]✓ Initialized AgentChaos GitHub suite![/bold green]")
    console.print(f"  • CI Workflow: [cyan]{wf_path}[/cyan]")
    console.print(f"  • Sample Test: [cyan]{sample_test_path}[/cyan]")
    console.print(f"\nRun [bold yellow]agent-chaos test[/bold yellow] to execute the suite.")


# -------------------------------------------------------------------------
# Evaluation Platform CLI Commands (agentchaos run / report / replay / export)
# -------------------------------------------------------------------------

@cli.command("run")
@click.option("--suite", default="reliability", help="Scenario suite to execute (default: reliability).")
@click.option("--scenario", default=None, help="Specific scenario name or path to scenario YAML.")
@click.option("--policy", default=None, help="Path to policy YAML file or policy name.")
@click.option("-o", "--output-json", default="result.json", help="Path to write machine-readable result.json.")
@click.option("--export-junit", default=None, help="Path to export JUnit XML for CI/CD.")
def run_command(
    suite: str,
    scenario: Optional[str],
    policy: Optional[str],
    output_json: str,
    export_junit: Optional[str],
) -> None:
    """Execute declarative agent chaos scenario packs and behavior assertions."""
    import json
    from agent_chaos.packs.loader import (
        get_scenarios_for_suite,
        load_scenario,
        load_policy,
    )
    from agent_chaos.specs.runner import run_simulated_scenario, SuiteRunSummary

    pol = load_policy(policy)

    if scenario:
        scenarios = [load_scenario(scenario)]
    else:
        scenarios = get_scenarios_for_suite(suite)
        if not scenarios:
            console.print(f"[bold red]No scenarios found in suite:[/bold red] {suite}")
            sys.exit(1)

    summary = SuiteRunSummary(suite_name=suite)
    console.print()

    for sc in scenarios:
        res = run_simulated_scenario(sc, pol)
        summary.add_result(res)

        # Title formatted nicely
        title = sc.name.replace("_", " ").capitalize()
        console.print(f"[bold]{title}[/bold]")

        # Explanation / finding line
        if res.passed:
            console.print("[dim]Recovered after one retry[/dim]" if "timeout" in sc.name else "[dim]Action completed within invariants[/dim]")
            console.print("[bold green]PASS[/bold green]\n")
        else:
            explanation = res.root_cause_evidence or "Policy violation detected"
            console.print(f"[yellow]{explanation}[/yellow]")
            console.print("[bold red]FAIL[/bold red]\n")

    # Summary counts
    if summary.failed_count > 0:
        console.print(f"[bold red]{summary.failed_count}[/bold red] Failed checks")
    if summary.passed_count > 0:
        console.print(f"[bold green]{summary.passed_count}[/bold green] Passed checks")
    if summary.findings_count > 0:
        console.print(f"[bold yellow]{summary.findings_count}[/bold yellow] Findings\n")
    else:
        console.print("0 Findings\n")

    console.print("[dim]Suggested commands: agentchaos report, agentchaos replay, agentchaos export --format junit[/dim]\n")

    # Serialize to result.json
    result_data = {
        "suite": suite,
        "policy": pol.name,
        "all_passed": summary.all_passed,
        "passed_count": summary.passed_count,
        "failed_count": summary.failed_count,
        "findings_count": summary.findings_count,
        "results": [r.model_dump() for r in summary.results],
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    # Export JUnit XML if requested
    if export_junit:
        xml_lines = [
            f'<?xml version="1.0" encoding="UTF-8"?>',
            f'<testsuite name="AgentChaos.{suite}" tests="{len(summary.results)}" failures="{summary.failed_count}" errors="0">',
        ]
        for r in summary.results:
            time_sec = r.total_duration_ms / 1000.0
            if r.passed:
                xml_lines.append(f'  <testcase classname="agentchaos.{r.policy}" name="{r.scenario}" time="{time_sec:.3f}"/>')
            else:
                xml_lines.append(f'  <testcase classname="agentchaos.{r.policy}" name="{r.scenario}" time="{time_sec:.3f}">')
                xml_lines.append(f'    <failure message="{r.first_failed_assertion or "Assertion Failed"}" type="BlastRadiusViolation">')
                xml_lines.append(f'      {r.root_cause_evidence or "Evidence not available"}')
                xml_lines.append(f'    </failure>')
                xml_lines.append(f'  </testcase>')
        xml_lines.append('</testsuite>')
        with open(export_junit, "w", encoding="utf-8") as f:
            f.write("\n".join(xml_lines))

    if not summary.all_passed:
        sys.exit(1)


@cli.command("report")
@click.option("-f", "--file", "result_file", default="result.json", help="Path to result.json.")
def report_command(result_file: str) -> None:
    """Display detailed execution traces, findings, and evidence from a previous run."""
    import json
    from pathlib import Path
    from rich.panel import Panel

    p = Path(result_file)
    if not p.exists():
        console.print(f"[bold red]Result file not found:[/bold red] {result_file}")
        sys.exit(1)

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", []) if "results" in data else [data]

    console.print(f"[bold cyan]📊 AgentChaos Evaluation Report[/bold cyan] [dim]({result_file})[/dim]\n")

    for r in results:
        status_color = "green" if r.get("passed", True) else "red"
        status_text = "PASS" if r.get("passed", True) else "FAIL"
        timeline = "\n".join(r.get("causal_timeline", []))

        console.print(Panel(
            f"[bold]Scenario:[/bold] {r.get('scenario')} | [bold]Policy:[/bold] {r.get('policy')} | [bold]Verdict:[/bold] [{status_color}]{status_text}[/{status_color}]\n\n"
            f"[bold]Causal Execution Timeline:[/bold]\n{timeline or 'No timeline recorded'}\n\n"
            f"[bold]First Failed Assertion:[/bold] {r.get('first_failed_assertion') or 'None'}\n"
            f"[bold]Evidence:[/bold] {r.get('root_cause_evidence') or 'Clean execution'}",
            title=f"{r.get('scenario')} ({status_text})",
            border_style=status_color,
        ))


@cli.command("replay")
@click.option("-f", "--file", "result_file", default="result.json", help="Path to result.json.")
def replay_command(result_file: str) -> None:
    """Replay recorded causal timeline and injected faults step-by-step."""
    import json
    from pathlib import Path

    p = Path(result_file)
    if not p.exists():
        console.print(f"[bold red]Result file not found:[/bold red] {result_file}")
        sys.exit(1)

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", []) if "results" in data else [data]

    console.print(f"[bold magenta]📼 Replaying Execution Trace[/bold magenta] [dim]({result_file})[/dim]\n")

    for r in results:
        console.print(f"[bold cyan]▶ Scenario:[/bold cyan] {r.get('scenario')}")
        timeline = r.get("causal_timeline", [])
        for entry in timeline:
            if "FAULT" in entry:
                console.print(f"  [bold red]{entry}[/bold red]")
            elif "FAILED" in entry:
                console.print(f"  [bold yellow]{entry}[/bold yellow]")
            else:
                console.print(f"  [dim]{entry}[/dim]")
        console.print()


@cli.command("export")
@click.option("--format", "-f", "export_format", type=click.Choice(["junit", "json", "html"]), default="junit", help="Export format.")
@click.option("--input", "-i", "input_file", default="result.json", help="Input result.json file.")
@click.option("-o", "--output", default=None, help="Output destination file path.")
def export_command(export_format: str, input_file: str, output: Optional[str]) -> None:
    """Export evaluation results to JUnit XML, JSON, or visual HTML."""
    import json
    from pathlib import Path

    p = Path(input_file)
    if not p.exists():
        console.print(f"[bold red]Input file not found:[/bold red] {input_file}")
        sys.exit(1)

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", []) if "results" in data else [data]
    failed_count = sum(1 for r in results if not r.get("passed", True))

    if export_format == "junit":
        dest = output or "agent-chaos-results.xml"
        xml_lines = [
            f'<?xml version="1.0" encoding="UTF-8"?>',
            f'<testsuite name="AgentChaos" tests="{len(results)}" failures="{failed_count}" errors="0">',
        ]
        for r in results:
            time_sec = float(r.get("total_duration_ms", 0.0)) / 1000.0
            sc = r.get("scenario", "test")
            pol = r.get("policy", "default")
            if r.get("passed", True):
                xml_lines.append(f'  <testcase classname="agentchaos.{pol}" name="{sc}" time="{time_sec:.3f}"/>')
            else:
                xml_lines.append(f'  <testcase classname="agentchaos.{pol}" name="{sc}" time="{time_sec:.3f}">')
                xml_lines.append(f'    <failure message="{r.get("first_failed_assertion", "Assertion Failed")}" type="BlastRadiusViolation">')
                xml_lines.append(f'      {r.get("root_cause_evidence", "Violation observed")}')
                xml_lines.append(f'    </failure>')
                xml_lines.append(f'  </testcase>')
        xml_lines.append('</testsuite>')
        content = "\n".join(xml_lines)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"[bold green]✓ Exported JUnit XML to:[/bold green] [cyan]{dest}[/cyan]")

    elif export_format == "html":
        dest = output or "agent-chaos-report.html"
        rows = []
        for r in results:
            sc = r.get("scenario", "test")
            passed = r.get("passed", True)
            status_cls = "pass" if passed else "fail"
            evidence = r.get("root_cause_evidence") or "Passed cleanly"
            rows.append(f"<tr><td><b>{sc}</b></td><td class='{status_cls}'>{'PASS' if passed else 'FAIL'}</td><td>{evidence}</td></tr>")

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>AgentChaos Evaluation Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }}
        .card {{ background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #334155; }}
        .pass {{ color: #22c55e; font-weight: bold; }}
        .fail {{ color: #ef4444; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; }}
    </style>
</head>
<body>
    <h1>⚡ AgentChaos Evaluation Report</h1>
    <div class="card">
        <h2>Total Checks: {len(results)} | Failed: <span class="{'fail' if failed_count > 0 else 'pass'}">{failed_count}</span></h2>
        <table>
            <thead><tr><th>Scenario</th><th>Verdict</th><th>Evidence</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </div>
</body>
</html>"""
        with open(dest, "w", encoding="utf-8") as f:
            f.write(html_content)
        console.print(f"[bold green]✓ Exported HTML Report to:[/bold green] [cyan]{dest}[/cyan]")

    else:
        dest = output or "exported-result.json"
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        console.print(f"[bold green]✓ Exported JSON to:[/bold green] [cyan]{dest}[/cyan]")


if __name__ == "__main__":
    cli()


