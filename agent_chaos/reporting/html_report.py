"""HTML report generator for AgentChaos trajectories and blast-radius audits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

from agent_chaos.core.assertions import _extract_recorder
from agent_chaos.core.trajectory import TrajectoryRecorder
from agent_chaos.security.redteam import RedTeamReport


def generate_html_report(
    target: Any,
    output_file: str = "agent-chaos-report.html",
    title: str = "AgentChaos Reliability & Blast-Radius Report",
) -> str:
    """Generate a self-contained, responsive HTML trajectory report."""
    if isinstance(target, RedTeamReport):
        html = _render_redteam_html(target, title)
    else:
        recorder = _extract_recorder(target)
        html = _render_trajectory_html(recorder, title)

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return str(out_path.resolve())


def _render_trajectory_html(recorder: TrajectoryRecorder, title: str) -> str:
    total_calls = recorder.total_calls()
    faulted_calls = sum(1 for e in recorder.events if e.fault_injected is not None)
    fault_rate = (faulted_calls / total_calls * 100.0) if total_calls > 0 else 0.0
    avg_latency = (
        sum(e.duration_ms for e in recorder.events) / total_calls if total_calls > 0 else 0.0
    )

    rows = []
    for e in recorder.events:
        fault_badge = (
            f'<span class="badge badge-fault">{e.fault_injected.value.upper()}</span>'
            if e.fault_injected
            else '<span class="badge badge-normal">PASSED</span>'
        )

        status_class = "event-faulted" if e.fault_injected else "event-passed"
        args_str = json.dumps(e.arguments, indent=2)
        res_str = json.dumps(e.result, indent=2) if e.result is not None else (e.error or "None")

        rows.append(f"""
        <div class="timeline-item {status_class}">
            <div class="timeline-header">
                <span class="step-num">#{e.global_index}</span>
                <span class="tool-name">{e.tool_name}</span>
                {fault_badge}
                <span class="duration">{e.duration_ms:.1f}ms</span>
            </div>
            <div class="timeline-body">
                <div class="code-block">
                    <strong>Arguments:</strong>
                    <pre><code>{args_str}</code></pre>
                </div>
                <div class="code-block">
                    <strong>Response / Status:</strong>
                    <pre><code>{res_str}</code></pre>
                </div>
            </div>
        </div>
        """)

    timeline_html = "\n".join(rows) if rows else "<p class='empty-state'>No tool invocations recorded.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-border: #334155;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --cyan: #38bdf8;
            --red: #f87171;
            --green: #4ade80;
            --yellow: #facc15;
        }}
        body {{
            background-color: var(--bg);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 32px 16px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 32px;
            border-bottom: 1px solid var(--surface-border);
            padding-bottom: 20px;
        }}
        h1 {{
            margin: 0 0 8px 0;
            color: var(--cyan);
            font-size: 26px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 8px;
            padding: 16px;
        }}
        .stat-title {{
            font-size: 13px;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .stat-val {{
            font-size: 26px;
            font-weight: bold;
            margin-top: 4px;
        }}
        .timeline {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .timeline-item {{
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 8px;
            padding: 16px;
        }}
        .timeline-item.event-faulted {{
            border-left: 4px solid var(--red);
        }}
        .timeline-item.event-passed {{
            border-left: 4px solid var(--green);
        }}
        .timeline-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}
        .step-num {{
            color: var(--text-dim);
            font-size: 14px;
            font-weight: bold;
        }}
        .tool-name {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-main);
        }}
        .badge {{
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 4px;
            letter-spacing: 0.5px;
        }}
        .badge-fault {{
            background: rgba(248, 113, 113, 0.2);
            color: var(--red);
        }}
        .badge-normal {{
            background: rgba(74, 222, 128, 0.2);
            color: var(--green);
        }}
        .duration {{
            margin-left: auto;
            color: var(--text-dim);
            font-size: 13px;
        }}
        .timeline-body {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}
        @media (max-width: 600px) {{
            .timeline-body {{ grid-template-columns: 1fr; }}
        }}
        .code-block pre {{
            background: #090d16;
            padding: 10px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 12px;
            color: #cbd5e1;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚡ {title}</h1>
            <p style="color: var(--text-dim); margin: 0;">Deterministic tool interception & blast-radius audit</p>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">Total Tool Calls</div>
                <div class="stat-val" style="color: var(--cyan);">{total_calls}</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">Injected Faults</div>
                <div class="stat-val" style="color: var(--red);">{faulted_calls}</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">Fault Rate</div>
                <div class="stat-val" style="color: var(--yellow);">{fault_rate:.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">Avg Tool Latency</div>
                <div class="stat-val">{avg_latency:.1f}ms</div>
            </div>
        </div>

        <h2 style="font-size: 18px; margin-bottom: 16px;">Execution Trajectory</h2>
        <div class="timeline">
            {timeline_html}
        </div>
    </div>
</body>
</html>
"""


def _render_redteam_html(report: RedTeamReport, title: str) -> str:
    color = "var(--green)" if report.passed else "var(--red)"
    rows = []
    for r in report.results:
        status_badge = (
            '<span class="badge badge-normal">BLOCKED / SAFE</span>'
            if r.resisted
            else '<span class="badge badge-fault">BREACHED</span>'
        )
        reason = r.violation_reason or "Safely contained without unauthorized action."
        rows.append(f"""
        <div class="timeline-item {'event-passed' if r.resisted else 'event-faulted'}">
            <div class="timeline-header">
                <span class="step-num">{r.payload_id}</span>
                <span class="tool-name">{r.payload_name}</span>
                {status_badge}
                <span class="duration">{r.duration_ms:.1f}ms</span>
            </div>
            <div style="font-size: 13px; color: var(--text-dim); margin-bottom: 8px;">
                Category: <strong>{r.category.value}</strong>
            </div>
            <div style="font-size: 13px; color: #cbd5e1;">
                <strong>Audit Result:</strong> {reason}
            </div>
        </div>
        """)

    timeline_html = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-border: #334155;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --cyan: #38bdf8;
            --red: #f87171;
            --green: #4ade80;
        }}
        body {{
            background: var(--bg);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 32px 16px;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .stat-card {{ background: var(--surface); border: 1px solid var(--surface-border); border-radius: 8px; padding: 16px; }}
        .badge {{ font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; }}
        .badge-fault {{ background: rgba(248, 113, 113, 0.2); color: var(--red); }}
        .badge-normal {{ background: rgba(74, 222, 128, 0.2); color: var(--green); }}
        .timeline-item {{ background: var(--surface); border: 1px solid var(--surface-border); border-radius: 8px; padding: 16px; margin-bottom: 12px; }}
        .timeline-item.event-faulted {{ border-left: 4px solid var(--red); }}
        .timeline-item.event-passed {{ border-left: 4px solid var(--green); }}
        .timeline-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
        .step-num {{ font-weight: bold; color: var(--cyan); }}
        .tool-name {{ font-weight: 600; font-size: 15px; }}
        .duration {{ margin-left: auto; color: var(--text-dim); font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ {title}</h1>
        <p style="color: var(--text-dim); margin-top: -4px;">Automated Indirect Prompt Injection & Tool Vulnerability Matrix</p>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin: 24px 0;">
            <div class="stat-card">
                <div style="color: var(--text-dim); font-size: 12px;">Total Attacks</div>
                <div style="font-size: 26px; font-weight: bold; color: var(--cyan);">{report.total_attacks}</div>
            </div>
            <div class="stat-card">
                <div style="color: var(--text-dim); font-size: 12px;">Attacks Resisted</div>
                <div style="font-size: 26px; font-weight: bold; color: var(--green);">{report.resisted_attacks}</div>
            </div>
            <div class="stat-card">
                <div style="color: var(--text-dim); font-size: 12px;">Security Breaches</div>
                <div style="font-size: 26px; font-weight: bold; color: var(--red);">{report.breached_attacks}</div>
            </div>
            <div class="stat-card">
                <div style="color: var(--text-dim); font-size: 12px;">Resilience Score</div>
                <div style="font-size: 26px; font-weight: bold; color: {color};">{report.resilience_score:.1f}%</div>
            </div>
        </div>

        <div class="timeline">
            {timeline_html}
        </div>
    </div>
</body>
</html>
"""
