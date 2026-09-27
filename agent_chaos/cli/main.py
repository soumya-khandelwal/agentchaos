"""CLI interface for AgentChaos."""

from __future__ import annotations

import sys
import click
import pytest
from rich.console import Console
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


if __name__ == "__main__":
    cli()
