"""HTML Report Generator for Native Salesforce Agentforce Reliability Audits."""

from __future__ import annotations

import json
from pathlib import Path
from agent_chaos.salesforce.native.runner import NativeScenarioReport


HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Agentforce Native Reliability Report: {scenario_name}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090d16;
      --card: #161e31;
      --border: rgba(255, 255, 255, 0.08);
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --success: #34d399;
      --danger: #f87171;
      --warning: #fbbf24;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 2.5rem;
      line-height: 1.6;
    }
    .container { max-width: 1000px; margin: 0 auto; }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border);
    }
    .title h1 {
      font-size: 1.8rem;
      font-weight: 800;
      color: #fff;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.4rem 1rem;
      border-radius: 999px;
      font-weight: 700;
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .badge-pass { background: rgba(52, 211, 153, 0.15); border: 1px solid rgba(52, 211, 153, 0.3); color: var(--success); }
    .badge-fail { background: rgba(248, 113, 113, 0.15); border: 1px solid rgba(248, 113, 113, 0.3); color: var(--danger); }
    
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.25rem; margin-bottom: 2rem; }
    .stat-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem;
    }
    .stat-card .label { font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; }
    .stat-card .value { font-size: 1.7rem; font-weight: 800; color: #fff; margin-top: 0.25rem; }

    .diagnosis-box {
      background: rgba(56, 189, 248, 0.08);
      border: 1px solid rgba(56, 189, 248, 0.2);
      border-radius: 10px;
      padding: 1.25rem;
      margin-bottom: 2.5rem;
      font-weight: 600;
      color: #e0f2fe;
    }

    .section-title { font-size: 1.3rem; font-weight: 700; margin-bottom: 1rem; color: #fff; }
    
    .turn-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }
    .turn-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border);
    }
    .turn-prompt {
      background: rgba(0, 0, 0, 0.3);
      padding: 0.85rem 1rem;
      border-radius: 8px;
      margin-bottom: 0.75rem;
      font-size: 0.95rem;
      border-left: 3px solid var(--accent);
    }
    .turn-response {
      background: rgba(255, 255, 255, 0.03);
      padding: 0.85rem 1rem;
      border-radius: 8px;
      margin-bottom: 1rem;
      font-size: 0.95rem;
      border-left: 3px solid #818cf8;
    }

    table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.88rem; }
    th, td { padding: 0.6rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
    th { color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; font-weight: 700; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">
        <h1>🐒⚡ AgentChaos: Native Agentforce Audit</h1>
        <p style="color: var(--text-muted); font-size: 0.9rem;">Scenario: <strong>{scenario_name}</strong></p>
      </div>
      <div>
        {status_badge}
      </div>
    </div>

    <div class="grid">
      <div class="stat-card">
        <div class="label">Total Evaluated Turns</div>
        <div class="value">{total_turns}</div>
      </div>
      <div class="stat-card">
        <div class="label">Passed Reliability Checks</div>
        <div class="value">{passed_turns} / {total_turns}</div>
      </div>
      <div class="stat-card">
        <div class="label">Experience Cloud SLA</div>
        <div class="value" style="{exp_cloud_style}">{exp_cloud_status}</div>
      </div>
    </div>

    <div class="diagnosis-box">
      {diagnosis}
    </div>

    <h2 class="section-title">Conversational Turns &amp; SLA Breakdown</h2>
    {turns_html}
  </div>
</body>
</html>
"""


def generate_native_html_report(report: NativeScenarioReport, output_file: str | Path) -> str:
    """Generate a self-contained HTML audit dashboard for native Agentforce testing."""
    target_path = Path(output_file)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    status_badge = (
        '<div class="badge badge-pass">● ALL CHECKS PASSED</div>'
        if report.all_passed
        else '<div class="badge badge-fail">● FAILURE DETECTED</div>'
    )

    exp_status = "COMPLIANT (15s)" if report.experience_cloud_compatible else "DROPPED (>15s)"
    exp_style = "color: #34d399;" if report.experience_cloud_compatible else "color: #f87171;"

    turns_blocks = []
    for t in report.turns:
        sla_rows = []
        for ch in t.sla_report.channel_evaluations:
            status_text = '<span style="color: #34d399; font-weight: 700;">PASS</span>' if ch.passed else '<span style="color: #f87171; font-weight: 700;">FAIL</span>'
            sla_rows.append(
                f"<tr><td>{ch.channel_name}</td><td>{ch.budget_seconds:.1f}s</td>"
                f"<td>{t.duration_seconds:.2f}s</td><td>{status_text}</td></tr>"
            )

        violations_html = ""
        if t.audit_report.violations:
            v_list = "".join(f"<li style='color: #f87171;'>[{v.rule_name}] {v.message}</li>" for v in t.audit_report.violations)
            violations_html = f"<div style='margin-top: 0.75rem;'><strong style='color: #f87171;'>Violations:</strong><ul>{v_list}</ul></div>"

        turns_blocks.append(
            f"""
            <div class="turn-card">
              <div class="turn-header">
                <strong>Turn #{t.step_index}</strong>
                <span style="font-size: 0.85rem; font-weight: 700; color: {'#34d399' if t.passed else '#f87171'};">
                  {'PASS' if t.passed else 'FAIL'} ({t.duration_seconds:.2f}s)
                </span>
              </div>
              <div class="turn-prompt"><strong>User:</strong> {t.user_query}</div>
              <div class="turn-response"><strong>Agentforce:</strong> {t.agent_response}</div>
              {violations_html}
              <table>
                <thead>
                  <tr><th>Channel</th><th>Budget</th><th>Actual Duration</th><th>SLA Status</th></tr>
                </thead>
                <tbody>
                  {''.join(sla_rows)}
                </tbody>
              </table>
            </div>
            """
        )

    rendered = (
        HTML_REPORT_TEMPLATE
        .replace("{scenario_name}", report.scenario_name)
        .replace("{status_badge}", status_badge)
        .replace("{total_turns}", str(report.total_turns))
        .replace("{passed_turns}", str(report.passed_turns))
        .replace("{exp_cloud_status}", exp_status)
        .replace("{exp_cloud_style}", exp_style)
        .replace("{diagnosis}", report.overall_diagnosis)
        .replace("{turns_html}", "\n".join(turns_blocks))
    )

    target_path.write_text(rendered, encoding="utf-8")
    return str(target_path.resolve())
