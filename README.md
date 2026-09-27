# AgentChaos 🐒⚡

> **Open-Source Fault Injection & Blast-Radius Testing for AI Agents.**  
> Test how your autonomous agents behave when tools fail, APIs time out, or external data is corrupted.

---

## ⚡ Quick Start (30 Seconds)

### 1. Installation
```bash
pip install -e .
```

### 2. Run Existing Tests
```bash
agent-chaos test
```

### 3. Basic Usage
```python
from agent_chaos import ChaosHarness, Fault, assert_tool_called, assert_max_retries

# 1. Initialize harness
harness = ChaosHarness()

# 2. Inject 504 Gateway Timeout (fails once, then recovers)
harness.set_fault("payment_api", Fault.http_error(status_code=504, times=1))

# 3. Wrap your agent's tool
wrapped_payment = harness.wrap_tool("payment_api", real_payment_func)

# 4. Run your agent & verify resilience
run_my_agent(tools=[wrapped_payment])
assert_tool_called(harness, "payment_api", times=2)
assert_max_retries(harness, "payment_api", max_retries=3)
```

### 4. MCP (Model Context Protocol) Chaos Gateway
```bash
# Intercept Claude Desktop / Cursor MCP tool calls transparently
agent-chaos mcp --target "python my_mcp_server.py" --fault-tool "refund_api" --fault-type "timeout" --delay 2.0
```

### 5. Automated Security Red-Teaming & HTML Report
```python
from agent_chaos.security import RedTeamSuite
from agent_chaos.reporting import generate_html_report

suite = RedTeamSuite(target_tool="read_email", forbidden_tools=["wire_transfer"])
report = suite.run(run_agent)
generate_html_report(report, "security-report.html")
```

### 6. Interactive Terminal UI & Runtime Guard
```bash
# Launch the interactive live tool traffic monitor and circuit breaker console
agent-chaos tui
```

---

## 📖 Bite-Sized Documentation Guide

The documentation is split into 4 short, focused modules:

| # | Guide | What You'll Learn | Reading Time |
| :---: | :--- | :--- | :--- |
| **01** | [**Concepts & Failure Modes**](docs/01-concepts.md) | Why agents break, the 4 silent failure modes in production. | 2 mins |
| **02** | [**Architecture & Design**](docs/02-architecture.md) | How the proxy interceptor, MCP gateway, and assertion engine work. | 3 mins |
| **03** | [**Guided Code Walkthrough**](docs/03-code-walkthrough.md) | 5-file tour of the codebase + 4 hands-on terminal experiments. | 4 mins |
| **04** | [**Testing Guide & Catalog**](docs/04-testing.md) | Command cheat sheet, catalog of all 33 tests, and how to write new tests. | 3 mins |

---

## 🗺️ Project Status

* [x] **v0.1 Developer Core:** Local fault injection, function interceptor, deterministic assertions, pytest plugin, CLI.
* [x] **v0.2 Universal MCP Gateway:** Stdio JSON-RPC duplex proxy for Cursor, Claude Desktop, and Model Context Protocol servers.
* [x] **v0.3 CI/CD & Security:** Automated GitHub Actions, indirect prompt injection suites, HTML trajectory visualizer, JUnit export.
* [x] **v1.0 Production Runtime Guard & TUI:** In-line circuit breakers, sliding-window rate limiters, HITL gates, and interactive terminal dashboard.
