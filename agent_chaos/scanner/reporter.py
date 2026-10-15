"""Rich terminal display and HTML scorecard reporting for AgentScanner."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from agent_chaos.scanner.runner import ScanReport

console = Console()


def print_scan_report(report: ScanReport) -> None:
    """Render a beautiful Rich terminal table and summary card for scan results."""
    color = "green" if report.passed else "red"
    status_text = "PASSED - PRODUCTION READY" if report.passed else "FAILED - HIGH RISK VULNERABILITIES"

    console.print(f"\n[bold cyan]⚡ AgentChaos Security & Resilience Scan[/bold cyan]")
    console.print(f"[dim]Target: {report.target} | Battery: {report.suite}[/dim]\n")

    table = Table(title="Chaos Scenario Breakdown", border_style="dim")
    table.add_column("#", style="dim", width=4)
    table.add_column("Vector / Scenario", style="bold", width=30)
    table.add_column("Category", width=12)
    table.add_column("Status", width=10)
    table.add_column("Audit Finding", width=45)

    for idx, f in enumerate(report.findings, start=1):
        status_badge = "[green]✓ PASS[/green]" if f.passed else "[red]✗ FAIL[/red]"
        table.add_row(
            str(idx),
            f.name,
            f.category,
            status_badge,
            f.details,
        )

    console.print(table)

    summary_panel = Panel(
        f"[bold]Target:[/bold] {report.target}\n"
        f"[bold]Battery:[/bold] {report.suite} ({report.passed_scenarios}/{report.total_scenarios} scenarios clean)\n"
        f"[bold]Resilience Score:[/bold] [{color}]{report.safety_score:.1f}%[/{color}]\n"
        f"[bold]Overall Verdict:[/bold] [{color}]{status_text}[/{color}]",
        title="[bold]🛡️ Agent Safety Scorecard[/bold]",
        border_style=color,
    )
    console.print(summary_panel)

    if report.remediations:
        console.print("\n[bold yellow]🛠️ Actionable Remediation Recipes:[/bold yellow]")
        for rem in report.remediations:
            console.print(f"  • {rem}")


def export_scan_html(report: ScanReport, output_path: str = "agent-chaos-report.html") -> None:
    """Export visual HTML scorecard for GitHub Actions and CI artifacts."""
    pass_color = "#22c55e" if report.passed else "#ef4444"
    status_label = "READY FOR PRODUCTION" if report.passed else "CRITICAL VULNERABILITIES DETECTED"

    rows_html = ""
    for idx, f in enumerate(report.findings, start=1):
        status_cls = "pass" if f.passed else "fail"
        status_text = "PASS" if f.passed else "FAIL"
        rows_html += f"""
        <tr>
            <td>{idx}</td>
            <td><b>{f.name}</b></td>
            <td><span class="badge">{f.category}</span></td>
            <td class="{status_cls}">{status_text}</td>
            <td>{f.details}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>AgentChaos Safety Scorecard: {report.target}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; max-width: 1000px; margin: 0 auto; }}
        .header {{ margin-bottom: 2rem; border-bottom: 1px solid #334155; padding-bottom: 1rem; }}
        .score-card {{ background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; border: 1px solid #334155; }}
        .score {{ font-size: 3rem; font-weight: 800; color: {pass_color}; }}
        .badge {{ background: #334155; color: #94a3b8; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; background: #1e293b; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 0.85rem 1rem; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #0f172a; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }}
        .pass {{ color: #22c55e; font-weight: bold; }}
        .fail {{ color: #ef4444; font-weight: bold; }}
        .remediation {{ background: #1e293b; border-left: 4px solid #f59e0b; padding: 1rem; margin-top: 2rem; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ AgentChaos Safety Scorecard</h1>
        <p style="color: #94a3b8;">Automated Fault Injection & Blast Radius Audit</p>
    </div>
    <div class="score-card">
        <div>Target: <b>{report.target}</b> | Suite: <b>{report.suite}</b></div>
        <div class="score">{report.safety_score:.1f}%</div>
        <div style="font-weight: 600; color: {pass_color};">{status_label}</div>
        <p style="color: #94a3b8;">{report.passed_scenarios} of {report.total_scenarios} failure modes verified resilient.</p>
    </div>
    <table>
        <thead>
            <tr><th>#</th><th>Scenario</th><th>Category</th><th>Status</th><th>Audit Details</th></tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    console.print(f"[bold green]✓ Visual HTML Scorecard exported to:[/bold green] [cyan]file://{output_path}[/cyan]")
