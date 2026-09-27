# 03. Guided Code Walkthrough

> **TL;DR:** Don't read the whole repo at once. Follow this 4-file tour to understand how everything connects in under 5 minutes.

---

## 🗺️ The 4-File Reading Order

### 1. `agent_chaos/core/faults.py` — The Fault Definitions
* **Open:** [`agent_chaos/core/faults.py`](file:///home/soumikhandelwal/agent-chaos/agent_chaos/core/faults.py#L46-L105)
* **Look at:** The factory methods on lines 46–105 (`Fault.timeout`, `Fault.http_error`, `Fault.rate_limit`).
* **Key Concept:** Notice `times: Optional[int] = None`. If you omit `times`, the fault happens on every call. If you set `times=1`, it fails once and then recovers, allowing you to test retry loops.

---

### 2. `agent_chaos/core/interceptor.py` — The Function Interceptor
* **Open:** [`agent_chaos/core/interceptor.py`](file:///home/soumikhandelwal/agent-chaos/agent_chaos/core/interceptor.py#L59-L85)
* **Look at:** `wrap_tool()` and `_extract_args()` on lines 59–85.
* **Key Concept:** `inspect.signature(func).bind_partial(*args, **kwargs)` converts all inputs into a clean dictionary. It wraps both `async def` and regular `def` tools cleanly.

---

### 3. `agent_chaos/core/assertions.py` — Blast Radius Assertions
* **Open:** [`agent_chaos/core/assertions.py`](file:///home/soumikhandelwal/agent-chaos/agent_chaos/core/assertions.py#L48-L77)
* **Look at:** `assert_parameters_match` and `assert_max_retries`.
* **Key Concept:** Zero LLM judge tokens used. These are fast, deterministic Python checks against recorded trajectory logs.

---

### 4. `tests/test_agent_scenarios.py` — The End-to-End Simulation
* **Open:** [`tests/test_agent_scenarios.py`](file:///home/soumikhandelwal/agent-chaos/tests/test_agent_scenarios.py#L65-L105)
* **Look at:** `test_agent_graceful_degradation_under_chaos()` on lines 65–105.
* **Key Concept:** This ties everything together: an agent attempts a refund, gets hit with an injected 504 Gateway Timeout, and gracefully degrades to creating an investigation ticket.

---

### 5. `agent_chaos/mcp/stdio_proxy.py` — The MCP Chaos Gateway
* **Open:** [`agent_chaos/mcp/stdio_proxy.py`](file:///home/soumikhandelwal/agent-chaos/agent_chaos/mcp/stdio_proxy.py)
* **Look at:** `run_streams()` and `_handle_client_to_server()`.
* **Key Concept:** Plugs between any MCP client (Claude Desktop / Cursor) and MCP server, parsing JSON-RPC messages and injecting synthetic faults before tools ever touch backend resources.

---

## 🧪 4 Hands-On Terminal Experiments

Try these in your terminal to see AgentChaos catch real violations:

### Experiment 1: Trigger a Blast-Radius Policy Violation
1. In [`tests/test_agent_scenarios.py`](file:///home/soumikhandelwal/agent-chaos/tests/test_agent_scenarios.py#L96), change `<= 500` to `<= 200`:
   ```python
   assert_parameters_match(harness, "process_refund", lambda args: args.get("amount", 0) <= 200)
   ```
2. Run: `pytest -s tests/test_agent_scenarios.py`
3. **What happens:** Fails with `BlastRadiusViolation: Parameter validation failed: Agent attempted to refund amount greater than authorized limit of $500`.
4. *(Revert the change back to 500 afterwards).*

### Experiment 2: Trigger a Runaway Retry Violation
1. In [`tests/test_agent_scenarios.py`](file:///home/soumikhandelwal/agent-chaos/tests/test_agent_scenarios.py#L93), change `max_retries=2` to `max_retries=1`:
   ```python
   assert_max_retries(harness, "process_refund", max_retries=1)
   ```
2. Run: `pytest`
3. **What happens:** Fails with `Runaway retry loop detected! Tool 'process_refund' was called 2 times (maximum allowed retries was 1)`.

### Experiment 3: View the Trajectory Visualizer
Run:
```bash
pytest -v -s tests/test_agent_scenarios.py
```
Notice the color-coded terminal table showing millisecond durations, argument payloads, and fault badges.

### Experiment 4: Intercept MCP Tools from the Terminal
Run:
```bash
agent-chaos mcp --target "python mock_server.py" --fault-tool "transfer" --fault-type "http_error" --status-code 500
```
Claude Desktop or Cursor will automatically receive synthetic `500 Internal Server Error` responses when calling `transfer`, testing your agent's fault tolerance without any code changes!

---

[← Previous: 02. Architecture](02-architecture.md) | [Next: 04. Testing Guide →](04-testing.md)
