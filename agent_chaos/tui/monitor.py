"""Interactive Terminal UI (TUI) for real-time tool traffic monitoring and circuit breakers."""

from __future__ import annotations

import time
from typing import Dict, List, Optional
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from agent_chaos.guard.circuit_breaker import CircuitBreaker, CircuitState


class TerminalMonitor:
    """Renders a real-time terminal dashboard of tool traffic, circuit breakers, and guardrails."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()
        self.events: List[Dict[str, str]] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def add_event(self, tool_name: str, args: str, status: str, duration: str) -> None:
        """Log a new tool invocation event into the live stream."""
        self.events.append({
            "time": time.strftime("%H:%M:%S"),
            "tool": tool_name,
            "args": args[:30] + ("..." if len(args) > 30 else ""),
            "status": status,
            "duration": duration,
        })
        if len(self.events) > 15:
            self.events.pop(0)

    def register_circuit_breaker(self, cb: CircuitBreaker) -> None:
        self.circuit_breakers[cb.tool_name] = cb

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3),
        )
        layout["main"].split_row(
            Layout(name="traffic", ratio=2),
            Layout(name="guards", ratio=1),
        )

        # 1. Header
        layout["header"].update(
            Panel(
                "[bold cyan]AgentChaos[/bold cyan] [bold white]Interactive Runtime Guard & Chaos Console (v1.0.0)[/bold white]",
                border_style="cyan",
            )
        )

        # 2. Traffic Stream
        traffic_table = Table(title="Live Tool Execution Stream", expand=True, border_style="blue")
        traffic_table.add_column("Time", style="dim", width=8)
        traffic_table.add_column("Tool", style="bold white", width=18)
        traffic_table.add_column("Arguments", style="dim")
        traffic_table.add_column("Status", width=14)
        traffic_table.add_column("Latency", justify="right", width=8)

        for ev in reversed(self.events[-8:]):
            color = "green" if "OK" in ev["status"] else "red"
            traffic_table.add_row(
                ev["time"],
                ev["tool"],
                ev["args"],
                f"[{color}]{ev['status']}[/{color}]",
                ev["duration"],
            )

        layout["traffic"].update(Panel(traffic_table, border_style="blue"))

        # 3. Guardrails & Circuit Breakers
        guard_table = Table(title="Circuit Breakers", expand=True, border_style="magenta")
        guard_table.add_column("Tool", style="bold white")
        guard_table.add_column("State", width=12)
        guard_table.add_column("Failures", justify="center", width=8)

        for name, cb in self.circuit_breakers.items():
            if cb.state == CircuitState.CLOSED:
                state_str = "[green]● CLOSED[/green]"
            elif cb.state == CircuitState.OPEN:
                state_str = "[red]✖ OPEN[/red]"
            else:
                state_str = "[yellow]▲ HALF_OPEN[/yellow]"

            guard_table.add_row(name, state_str, f"{cb.failure_count}/{cb.failure_threshold}")

        layout["guards"].update(Panel(guard_table, border_style="magenta"))

        # 4. Footer
        layout["footer"].update(
            Panel(
                "[dim]Status: [green]Active[/green] | Auto-healing: [cyan]Enabled[/cyan] | Press [bold white]Ctrl+C[/bold white] to exit console[/dim]",
                border_style="dim",
            )
        )

        return layout

    def run_demo(self, iterations: int = 15) -> None:
        """Run an interactive live visualization demo."""
        import random

        cb_stripe = CircuitBreaker(tool_name="stripe_charge", failure_threshold=3, recovery_timeout=5.0)
        cb_crm = CircuitBreaker(tool_name="crm_lookup", failure_threshold=2, recovery_timeout=4.0)
        self.register_circuit_breaker(cb_stripe)
        self.register_circuit_breaker(cb_crm)

        with Live(self.make_layout(), console=self.console, refresh_per_second=4, screen=False) as live:
            for i in range(iterations):
                # Simulate calls
                tool = random.choice(["stripe_charge", "crm_lookup", "check_inventory"])
                latency = f"{random.randint(15, 250)}ms"

                if tool == "stripe_charge":
                    cb = cb_stripe
                    if not cb.can_execute():
                        self.add_event(tool, '{"amount": 150}', "BLOCKED (CB)", "0.1ms")
                    else:
                        fail = random.random() < 0.6
                        if fail:
                            cb.record_failure()
                            self.add_event(tool, '{"amount": 150}', "FAULT (500)", latency)
                        else:
                            cb.record_success()
                            self.add_event(tool, '{"amount": 150}', "OK (200)", latency)

                elif tool == "crm_lookup":
                    cb = cb_crm
                    if not cb.can_execute():
                        self.add_event(tool, '{"id": "usr_42"}', "BLOCKED (CB)", "0.1ms")
                    else:
                        cb.record_success()
                        self.add_event(tool, '{"id": "usr_42"}', "OK (200)", latency)
                else:
                    self.add_event(tool, '{"sku": "SKU-99"}', "OK (200)", latency)

                live.update(self.make_layout())
                time.sleep(0.4)
