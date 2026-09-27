# 04. Testing Guide & Test Catalog

> **TL;DR:** Run `agent-chaos test` or `pytest -v -s` to execute the full suite in under 0.1s.

---

## ⚡ Quick Test Commands

```bash
# Run all tests via CLI
agent-chaos test

# Run tests with verbose output and visible tables
pytest -v -s

# Run only the end-to-end agent scenario test
pytest -v -s tests/test_agent_scenarios.py
```

---

## 📋 Catalog of Existing Test Cases (v0.2 — 21 Tests)

| File | Test Function | What Failure It Injects |
| :--- | :--- | :--- |
| `tests/test_faults.py` | `test_fault_factory_defaults` | Validates default triggers and fields |
| `tests/test_faults.py` | `test_fault_sync_execution` | Injects sync 500 error, timeout, and corrupt payload |
| `tests/test_faults.py` | `test_fault_async_execution` | Injects async 429 rate limit and timeout |
| `tests/test_interceptor.py` | `test_sync_tool_interception` | Normal execution $\rightarrow$ injected 500 error |
| `tests/test_interceptor.py` | `test_intermittent_fault_recovery` | Fails on call 1 $\rightarrow$ succeeds on call 2 (retry test) |
| `tests/test_interceptor.py` | `test_async_tool_interception` | Async timeout on call 1 $\rightarrow$ succeeds on call 2 |
| `tests/test_assertions.py` | `test_assert_tool_called_and_not_called` | Flags when a forbidden tool is called |
| `tests/test_assertions.py` | `test_assert_parameters_match` | Flags when tool parameters exceed safe policy |
| `tests/test_assertions.py` | `test_assert_max_retries` | Flags when agent enters infinite retry loop |
| `tests/test_assertions.py` | `test_assert_sequence` | Flags when tools are called in illegal order |
| `tests/test_agent_scenarios.py` | `test_agent_graceful_degradation` | 504 Gateway Timeout during refund workflow |
| `tests/test_mcp_interceptor.py` | `test_mcp_interceptor_non_tool_call_ignored` | Ensures `initialize` & `tools/list` pass through |
| `tests/test_mcp_interceptor.py` | `test_mcp_interceptor_unmatched_tool_passed_through` | Verifies non-targeted tools are unaffected |
| `tests/test_mcp_interceptor.py` | `test_mcp_interceptor_mcp_error_response` | Injects MCP `isError: true` tool error response |
| `tests/test_mcp_interceptor.py` | `test_mcp_interceptor_jsonrpc_protocol_error` | Injects standard JSON-RPC `-32000` protocol error |
| `tests/test_mcp_interceptor.py` | `test_mcp_interceptor_intermittent_fault` | Injects fault once (`times=1`) then allows retry |
| `tests/test_mcp_interceptor.py` | `test_mcp_interceptor_poisoned_payload` | Injects indirect prompt injection into tool response |
| `tests/test_mcp_interceptor.py` | `test_mcp_interceptor_latency_pass_through` | Injects async delay before forwarding to server |
| `tests/test_mcp_interceptor.py` | `test_mcp_interceptor_conditional_fault` | Triggers fault only when argument condition is met |
| `tests/test_mcp_proxy.py` | `test_mcp_proxy_interception_and_pass_through` | End-to-end stdio proxy interception with subprocess |
| `tests/test_mcp_proxy.py` | `test_mcp_proxy_intermittent_retry_success` | End-to-end retry loop through stdio proxy |
| `tests/test_redteam.py` | `test_builtin_payloads_catalog` | Validates adversarial attack vector catalog |
| `tests/test_redteam.py` | `test_redteam_suite_detects_vulnerable_agent` | Flags when agent executes unauthorized transfer |
| `tests/test_redteam.py` | `test_redteam_suite_validates_hardened_agent` | Validates agent resisting injection payloads |
| `tests/test_reporting.py` | `test_html_report_generation` | Generates self-contained HTML trajectory dashboard |
| `tests/test_reporting.py` | `test_junit_xml_export` | Exports valid JUnit XML for CI/CD pipelines |
| `tests/test_reporting.py` | `test_redteam_html_and_junit_export` | Exports security matrix HTML & JUnit reports |

---

## ✍️ Recipes: How to Test Your Agent

### Recipe A: Python Function / Decorator Wrapping
```python
from agent_chaos import ChaosHarness, Fault, assert_tool_called, assert_max_retries

def test_my_agent():
    harness = ChaosHarness()

    # 1. Choose a fault: 504 Gateway Timeout (intermittent: fails 1 time)
    harness.set_fault("payment_api", Fault.http_error(status_code=504, times=1))

    # 2. Wrap your tool
    wrapped_tool = harness.wrap_tool("payment_api", real_payment_function)

    # 3. Run your agent
    result = run_agent(tools=[wrapped_tool])

    # 4. Assert blast radius
    assert_tool_called(harness, "payment_api", times=2)
    assert_max_retries(harness, "payment_api", max_retries=3)
```

### Recipe B: Model Context Protocol (MCP) Server Testing
```bash
# Test an MCP server with a synthetic 500 error on the 'transfer' tool
agent-chaos mcp --target "python my_mcp_server.py" --fault-tool "transfer" --fault-type "http_error" --status-code 500
```

### Recipe C: Automated Indirect Prompt Injection Red-Teaming
```python
from agent_chaos.security import RedTeamSuite

def test_agent_injection_resilience():
    suite = RedTeamSuite(
        target_tool="read_email",
        forbidden_tools=["transfer_funds", "send_external_webhook"],
    )
    report = suite.run(my_agent_runner)
    assert report.passed, f"Security breach! Score: {report.resilience_score}%"
```

### Recipe D: Exporting Visual HTML Artifacts
```python
from agent_chaos.reporting import generate_html_report

generate_html_report(harness, output_file="agent-report.html")
```

---

[← Previous: 03. Code Walkthrough](03-code-walkthrough.md)
