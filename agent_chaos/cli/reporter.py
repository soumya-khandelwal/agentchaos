"""Rich terminal reporting and trajectory visualization for AgentChaos."""

from __future__ import annotations

import json
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent_chaos.core.interceptor import ChaosHarness

console = Console()


def render_trajectory_table(harness: ChaosHarness, title: str = "Agent Tool Trajectory Report") -> None:
    """Render a formatted Rich table of all intercepted tool events."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Tool Name", style="cyan")
    table.add_column("Arguments", style="white")
    table.add_column("Fault Injected", style="bold")
    table.add_column("Result / Status", style="green")
    table.add_column("Duration", style="yellow", justify="right")

    for event in harness.recorder.events:
        # Format arguments
        args_str = json.dumps(event.arguments, ensure_ascii=False)
        if len(args_str) > 40:
            args_str = args_str[:37] + "..."

        # Format fault
        if event.fault_injected:
            fault_text = Text(f"⚡ {event.fault_injected.value.upper()}", style="bold red")
        else:
            fault_text = Text("✓ Normal", style="dim green")

        # Format result / error
        if event.error:
            status_text = Text(f"ERR: {event.error[:30]}", style="red")
        elif event.result is not None:
            res_str = str(event.result)
            if len(res_str) > 30:
                res_str = res_str[:27] + "..."
            status_text = Text(res_str, style="green")
        else:
            status_text = Text("None", style="dim")

        duration_str = f"{event.duration_ms:.1f}ms"

        table.add_row(
            str(event.global_index),
            event.tool_name,
            args_str,
            fault_text,
            status_text,
            duration_str,
        )

    console.print(table)


def render_summary_panel(harness: ChaosHarness, test_name: Optional[str] = None) -> None:
    """Render an executive summary panel."""
    total_calls = harness.recorder.total_calls()
    total_faults = sum(1 for e in harness.recorder.events if e.fault_injected)

    summary_text = (
        f"[bold]Total Tool Calls:[/bold] {total_calls}\n"
        f"[bold]Faults Injected:[/bold] [red]{total_faults}[/red]\n"
        f"[bold]Status:[/bold] "
    )
    if total_faults > 0:
        summary_text += "[bold yellow]Resilience Tested[/bold yellow]"
    else:
        summary_text += "[dim]No Faults Triggered[/dim]"

    title = f"AgentChaos Summary: {test_name}" if test_name else "AgentChaos Summary"
    console.print(Panel(summary_text, title=title, border_style="cyan"))
