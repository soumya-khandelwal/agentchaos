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


if __name__ == "__main__":
    cli()
