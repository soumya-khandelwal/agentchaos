# 02. Architecture & Technical Design

> **TL;DR:** AgentChaos sits between your agent and its tools. It acts as a transparent proxy that can selectively inject faults (timeouts, HTTP errors, schema corruptions) and deterministically asserts that blast-radius rules are never breached.

---

## 1. System Architecture

```text
+-------------------------------------------------------------+
|                        Your AI Agent                        |
|        (LangGraph / CrewAI / Cursor / AutoGen / LLM)        |
+------------------------------+------------------------------+
                               |
                               | (Tool Invocations)
                               v
+-------------------------------------------------------------+
|                      AGENTCHAOS GATEWAY                     |
|                                                             |
|  [ Interceptor Proxy ]  --> Wraps any sync or async tool    |
|  [ Fault Engine ]       --> Injects 504s, 429s, latency     |
|  [ Trajectory Store ]   --> Logs arguments, timings, errors |
|  [ Blast Radius Engine ]--> Validates rules deterministically|
+------------------------------+------------------------------+
                               |
                               | (If no fault triggered)
                               v
+-------------------------------------------------------------+
|                  Real Tool / External API                   |
|                  (Stripe / CRM / Database)                  |
+-------------------------------------------------------------+
```

---

## 2. Tool Interception Flow

```text
  [AI Agent]               [Chaos Proxy]            [Fault Engine]       [Trajectory Store]
      |                          |                         |                       |
      | 1. Calls tool            |                         |                       |
      +------------------------->|                         |                       |
      |                          | 2. Check fault rules    |                       |
      |                          +------------------------>|                       |
      |                          |                         |                       |
      |                          |<------------------------+                       |
      |                          |    Fault? (e.g. 504)    |                       |
      |                          |                                                 |
      |                          | 3. Record call event                            |
      |                          +------------------------------------------------>|
      |                          |                                                 |
      | 4. Return fault/error    |                                                 |
      |<-------------------------+                                                 |
      |                          |                                                 |
      | (Agent catches error     |                                                 |
      |  and executes fallback)  |                                                 |
```

---

## 3. Core Components

### 1. `Fault` (`agent_chaos.core.faults`)
Defines the failure to inject.
* **Fault Types:** `TIMEOUT`, `HTTP_ERROR`, `RATE_LIMIT`, `MALFORMED_DATA`, `POISONED_PAYLOAD`, `LATENCY`.
* **Triggers:** `ALWAYS` (fails every time) or `times=1` (fails once, then recovers to test retries).

### 2. `ChaosHarness` (`agent_chaos.core.interceptor`)
The orchestration manager.
* Wraps tools via `harness.wrap_tool("tool_name", func)`.
* Uses `inspect.signature` to extract all arguments automatically.
* Supports both synchronous (`def`) and asynchronous (`async def`) functions.

### 3. `TrajectoryRecorder` (`agent_chaos.core.trajectory`)
In-memory event store.
* Records tool name, call index, passed arguments, latency (ms), and injected faults.

### 4. `Assertions` (`agent_chaos.core.assertions`)
Deterministic blast-radius checks (zero LLM tokens used):
* `assert_tool_called` & `assert_tool_not_called`
* `assert_parameters_match` (validates policies like `amount <= 500`)
* `assert_max_retries` (catches runaway retry loops)
* `assert_sequence` (enforces order like `auth` -> `charge`)
* Works seamlessly across both `ChaosHarness` and `MCPChaosProxy`.

### 5. `MCPChaosProxy` & `MCPFaultInterceptor` (`agent_chaos.mcp`)
Universal Stdio Gateway for Model Context Protocol (MCP) clients:
* Plugs transparently between MCP clients (Claude Desktop, Cursor, Antigravity) and any target MCP server.
* Duplex JSON-RPC 2.0 stdio interceptor requiring zero changes to client or server code.
* Injects synthetic MCP tool errors (`isError: true`), protocol errors (`-32000`), simulated latency, intermittent failures (`times=1`), and prompt injection payloads.
* Automatically records trajectory for contract assertions.

---

[<- Previous: 01. Concepts](01-concepts.md) | [Next: 03. Code Walkthrough ->](03-code-walkthrough.md)
